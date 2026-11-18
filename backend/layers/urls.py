from django.urls import path
from .views import (
    HealthView, PreviewView, LayersView, LayerDetailView,
    ReplaceView, FeaturesView, AttributesView, GeoServerHealthView, RasterTileView, RollbackView,
)

urlpatterns = [
    path('geoserver/health/', GeoServerHealthView.as_view()),
    path('layers/<uuid:layer_id>/tile/', RasterTileView.as_view()),
    path('layers/<uuid:layer_id>/rollback/', RollbackView.as_view()),
    path('health/', HealthView.as_view(), name='health'),
    path('layers/preview/', PreviewView.as_view(), name='preview'),
    path('layers/', LayersView.as_view(), name='layers'),
    path('layers/<uuid:layer_id>/', LayerDetailView.as_view(), name='layer-detail'),
    path('layers/<uuid:layer_id>/replace/', ReplaceView.as_view(), name='layer-replace'),
    path('layers/<uuid:layer_id>/features/', FeaturesView.as_view(), name='features'),
    path('layers/<uuid:layer_id>/attributes/', AttributesView.as_view(), name='attributes'),
]
