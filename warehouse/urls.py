from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SKUViewSet, LabelVersionViewSet, ShipmentBatchViewSet

router = DefaultRouter()
router.register(r'skus', SKUViewSet)
router.register(r'labels', LabelVersionViewSet)   # 对应 /api/labels/
router.register(r'batches', ShipmentBatchViewSet) # 对应 /api/batches/

urlpatterns = [
    path('', include(router.urls)),
]