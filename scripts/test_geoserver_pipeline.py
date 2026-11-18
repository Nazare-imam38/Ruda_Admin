"""Offline tests: mock the remote service; no Django/PostgreSQL/GeoServer needed.
Run from repository root: python scripts/test_geoserver_pipeline.py
"""
import io
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from layers.geoserver import GeoServer, canonical_zip, PublishError
from layers.importer import parse_shapefile, ImportValidationError
from layers.publishing import preview, publish_upload, rollback, ensure_compatible
from layers.raster import inspect_raster
ROOT=Path(__file__).resolve().parents[1]
SAMPLE=ROOT/'sample_data'/'01_Spot_Level_Points.zip'

class Upload(io.BytesIO):
    def __init__(self,p):
        data=p.read_bytes();super().__init__(data);self.name=p.name;self.size=len(data)
    def chunks(self):
        yield self.read()

def layer():
    return SimpleNamespace(group='Uploaded Layers',geometry_type='',source_crs='',source_filename='',field_names=[],field_schema=[],bbox=None,feature_count=0,publication={},publication_history=[],style={'color':'#ff0000'},show_attributes=True,show_popup=True,show_labels=False,label_field='',attribute_fields=[],popup_fields=[],version=1,save=Mock())

def fake_server():
    gs=Mock()
    gs.publish.side_effect=[{'kind':'wfs','workspace':'gis_lab','store':'one','name':'one'}, {'kind':'wfs','workspace':'gis_lab','store':'two','name':'two'}]
    parsed=parse_shapefile(SAMPLE.read_bytes())
    gs.features.return_value={'type':'FeatureCollection','totalFeatures':len(parsed.features),'features':[{'type':'Feature','geometry':parsed.features[0][0],'properties':parsed.features[0][1]}]}
    return gs

class TestPipeline(unittest.TestCase):
    def test_samples_roundtrip(self):
        for f in (ROOT/'sample_data').glob('*.zip'):
            p=parse_shapefile(f.read_bytes(),repair=False)
            q=parse_shapefile(canonical_zip(f.read_bytes(),'lab_demo'),repair=False)
            self.assertEqual(p.features,q.features)
            self.assertEqual(p.fields,q.fields)
    def test_preview(self):
        result=preview(Upload(SAMPLE))
        self.assertEqual(result['feature_count'],8)
        self.assertIn('zz',result['field_names'])
        self.assertEqual(len(result['preview_geojson']['features']),8)
    def test_publish_replace_rollback(self):
        gs=fake_server();record=layer()
        with patch('layers.publishing.GeoServer',return_value=gs):
            def configure(item): item.show_labels=True;item.label_field='zz'
            publish_upload(record,Upload(SAMPLE),configure=configure)
            self.assertEqual(record.publication['name'],'one')
            publish_upload(record,Upload(SAMPLE),replace=True)
            self.assertEqual(record.publication['name'],'two')
            self.assertEqual(record.label_field,'zz')
            self.assertEqual(record.style['color'],'#ff0000')
            rollback(record)
            self.assertEqual(record.publication['name'],'one')
            self.assertEqual(record.version,3)
    def test_failed_verification_no_metadata_save(self):
        gs=fake_server();gs.features.return_value={'features':[]};record=layer()
        with patch('layers.publishing.GeoServer',return_value=gs):
            with self.assertRaises(PublishError):publish_upload(record,Upload(SAMPLE))
        record.save.assert_not_called();gs.discard.assert_called_once()
    def test_incompatible_replacement(self):
        record=layer();record.geometry_type='Point';record.label_field='zz'
        with self.assertRaisesRegex(ImportValidationError,'missing configured fields'):
            ensure_compatible(record,{'geometry_type':'Point','field_names':['name']})
    def test_cadastral_not_accidentally_published(self):
        record=layer();record.group='Cadastral'
        with self.assertRaisesRegex(ImportValidationError,'relationship'):
            publish_upload(record,Upload(SAMPLE))
    def test_raster_metadata(self):
        data={'driverShortName':'GTiff','coordinateSystem':{'wkt':'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]'},'geoTransform':[74.29,.06/256,0,31.55,0,-.06/256],'size':[256,256],'bands':[{'type':'Byte'}]*3}
        import json
        with patch('layers.raster.gdal',return_value=json.dumps(data)):
            info=inspect_raster(ROOT/'sample_data'/'04_Test_Drone_Imagery.tif')
        self.assertEqual(info['raster']['bands'],3)
        self.assertAlmostEqual(info['bbox'][0],74.29)
    def test_http_contract_wfs(self):
        with patch.dict(os.environ,{'GEOSERVER_PASSWORD':'mock'}):
            gs=GeoServer();gs.session.request=Mock()
            gs.session.request.return_value=Mock(status_code=200,json=lambda:{'type':'FeatureCollection','features':[]})
            gs.features({'workspace':'gis_lab','name':'demo'},bbox=[74,31,75,32],count=20,start=40)
            args=gs.session.request.call_args.kwargs
            self.assertEqual(args['params']['startIndex'],40)
            self.assertEqual(args['params']['count'],20)
            self.assertEqual(args['params']['typeNames'],'gis_lab:demo')
            self.assertIn('CRS84',args['params']['bbox'])
    def test_raster_publication(self):
        gs=Mock();gs.publish.return_value={'kind':'wms','workspace':'gis_lab','store':'demo','name':'demo'}
        record=layer();meta={'geometry_type':'Raster','source_crs':'EPSG:4326','field_names':[],'field_schema':[],'bbox':[74.29,31.49,74.35,31.55],'feature_count':0,'raster':{'width':256,'height':256,'bands':3}}
        def fake_optimize(source,output):output.write_bytes(source.read_bytes())
        with patch('layers.publishing.GeoServer',return_value=gs),patch('layers.publishing.inspect_raster',return_value=meta),patch('layers.publishing.optimize',side_effect=fake_optimize):
            publish_upload(record,Upload(ROOT/'sample_data'/'04_Test_Drone_Imagery.tif'))
        self.assertEqual(record.publication['kind'],'wms');self.assertFalse(record.show_attributes);gs.image.assert_called_once()

if __name__=='__main__':unittest.main(verbosity=2)
