"""File-based GeoServer publishing for the local lab. Server credentials never reach React."""
import io
import os
import re
import zipfile
from uuid import uuid4
from urllib.parse import quote
import requests
from .importer import get_archive_files


class PublishError(ValueError):
    pass


def store_id():
    return 'lab_' + uuid4().hex


def canonical_zip(data, stem):
    # Forward only required file parts. Never forward arbitrary archive members.
    parts = get_archive_files(data)
    target = io.BytesIO()
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for suffix in ('.shp', '.shx', '.dbf', '.prj', '.cpg'):
            if suffix in parts:
                archive.writestr(stem + suffix, parts[suffix])
        if '.cpg' not in parts:
            archive.writestr(stem + '.cpg', b'UTF-8')
    return target.getvalue()


class GeoServer:
    def __init__(self):
        self.base = os.environ.get('GEOSERVER_URL', 'http://127.0.0.1:8080/geoserver').rstrip('/')
        self.workspace = os.environ.get('GEOSERVER_WORKSPACE', 'gis_lab')
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,39}', self.workspace):
            raise PublishError('Invalid GeoServer workspace setting.')
        password = os.environ.get('GEOSERVER_PASSWORD')
        if not password:
            raise PublishError('Set GEOSERVER_PASSWORD in backend/.env and restart Django.')
        self.session = requests.Session()
        self.session.auth = (os.environ.get('GEOSERVER_USER', 'admin'), password)
        self.ws = f'/rest/workspaces/{self.workspace}'

    def request(self, method, path, allowed=(200, 201, 202, 204), **kwargs):
        try:
            response = self.session.request(method, self.base + path, timeout=kwargs.pop('timeout', (8, 120)), allow_redirects=False, **kwargs)
        except requests.RequestException as exc:
            raise PublishError('GeoServer connection failed or timed out. Check URL, service and network.') from exc
        if response.status_code not in allowed:
            # Do not expose credential-bearing upstream diagnostics or server paths.
            raise PublishError(f'GeoServer {method} failed (HTTP {response.status_code}). Check GeoServer logs and permissions.')
        return response

    def json(self, response):
        try:
            data = response.json()
        except ValueError as exc:
            raise PublishError('GeoServer returned an unexpected non-JSON response.') from exc
        if not isinstance(data, dict):
            raise PublishError('Unexpected GeoServer JSON response.')
        return data

    def workspace_ready(self):
        response = self.request('GET', self.ws + '.json', allowed=(200, 404))
        if response.status_code == 404:
            self.request('POST', '/rest/workspaces', json={'workspace': {'name': self.workspace}})

    def health(self):
        self.request('GET', '/rest/workspaces.json', timeout=(4, 8))
        return self.workspace

    def publish(self, kind, data, name=None):
        self.workspace_ready()
        name = name or store_id()
        collection = 'datastores' if kind == 'wfs' else 'coveragestores'
        path = f'{self.ws}/{collection}/{name}'
        publication = {'kind': kind, 'workspace': self.workspace, 'store': name, 'name': '', 'collection': collection}
        try:
            if kind == 'wfs':
                self.request('PUT', path + '/file.shp', params={'configure': 'first'}, data=canonical_zip(data, name), headers={'Content-Type': 'application/zip'})
                response = self.json(self.request('GET', path + '/featuretypes.json'))
                entries = (response.get('featureTypes') or {}).get('featureType', [])
            else:
                with open(data, 'rb') as stream:
                    self.request('PUT', path + '/file.geotiff', params={'configure': 'first', 'coverageName': name}, data=stream, headers={'Content-Type': 'image/tiff'}, timeout=(8, 600))
                response = self.json(self.request('GET', path + '/coverages.json'))
                entries = (response.get('coverages') or {}).get('coverage', [])
            if isinstance(entries, dict):
                entries = [entries]
            if len(entries) != 1 or not entries[0].get('name'):
                raise PublishError('Expected exactly one published GeoServer layer in the new store.')
            publication['name'] = entries[0]['name']
            return publication
        except Exception:
            self.discard(publication)
            raise

    def discard(self, publication):
        # A failed cleanup should not hide the actual import failure. Never purge other stores.
        try:
            if publication['workspace'] != self.workspace or not re.fullmatch(r'lab_[a-f0-9]{32}', publication['store']):
                return False
            params = {'recurse': 'true'}
            if publication['collection'] == 'coveragestores':
                params['purge'] = 'all'
            self.request('DELETE', f'{self.ws}/{publication["collection"]}/{publication["store"]}', params=params, allowed=(200, 202, 204, 404))
            return True
        except (PublishError, KeyError):
            return False

    @staticmethod
    def qualified(publication):
        return publication['workspace'] + ':' + publication['name']

    def features(self, publication, bbox=None, count=100, start=0):
        params = {'service': 'WFS', 'version': '2.0.0', 'request': 'GetFeature',
                  'typeNames': self.qualified(publication), 'outputFormat': 'application/json',
                  'srsName': 'EPSG:4326', 'count': count, 'startIndex': start}
        # Force longitude-first OGC CRS84 in BBOX (WFS 2 axis order differs for EPSG URNs).
        if bbox is not None:
            params['bbox'] = ','.join(map(str, bbox)) + ',urn:ogc:def:crs:OGC:1.3:CRS84'
        data = self.json(self.request('GET', '/' + quote(publication['workspace'], safe='') + '/wfs', params=params))
        if data.get('type') != 'FeatureCollection' or not isinstance(data.get('features'), list):
            raise PublishError('GeoServer did not return a WFS GeoJSON FeatureCollection.')
        return data

    def image(self, publication, bbox, crs='EPSG:3857', size=256, image_format='image/png'):
        response = self.request('GET', '/' + quote(publication['workspace'], safe='') + '/wms', params={
            'service': 'WMS', 'version': '1.1.1', 'request': 'GetMap', 'layers': self.qualified(publication),
            'styles': '', 'srs': crs, 'bbox': ','.join(map(str, bbox)), 'width': size, 'height': size,
            'format': image_format, 'transparent': 'true'})
        if not response.headers.get('Content-Type', '').lower().startswith(image_format):
            raise PublishError('GeoServer WMS returned an error instead of an image.')
        return response.content
