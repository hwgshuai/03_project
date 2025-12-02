# warehouse/admin.py
from django import forms
from django.contrib import admin
from django.utils import timezone
from .models import SKU, LabelVersion, ShipmentBatch, Operator

@admin.register(Operator)
class OperatorAdmin(admin.ModelAdmin):
    list_display = ['username', 'full_name', 'email', 'is_active']
    search_fields = ['username', 'full_name']

class SKUAdminForm(forms.ModelForm):
    initial_fnsku = forms.CharField(max_length=100, required=False, label="Initial FNSKU")
    initial_upc = forms.CharField(max_length=100, required=False, label="Initial UPC")
    initial_created_by = forms.CharField(max_length=50, label="Created By", initial="admin")

    class Meta:
        model = SKU
        fields = ['sku_code', 'product_name']

class SKUAdmin(admin.ModelAdmin):
    form = SKUAdminForm
    list_display = ['sku_code', 'product_name', 'created_at']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            fnsku = form.cleaned_data.get('initial_fnsku', '')
            upc = form.cleaned_data.get('initial_upc', '')
            created_by = form.cleaned_data.get('initial_created_by', 'admin')
            LabelVersion.create_version(sku=obj, fnsku=fnsku, upc=upc, created_by=created_by)

class LabelVersionAdmin(admin.ModelAdmin):
    list_display = ['sku', 'version_number', 'fnsku', 'upc', 'checksum']
    readonly_fields = ['version_number', 'checksum']

    def has_change_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            LabelVersion.create_version(
                sku=obj.sku,
                fnsku=obj.fnsku,
                upc=obj.upc,
                created_by=obj.created_by
            )

class ShipmentBatchAdminForm(forms.ModelForm):
    class Meta:
        model = ShipmentBatch
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['reviewer1'].queryset = Operator.objects.filter(is_active=True)
        self.fields['reviewer2'].queryset = Operator.objects.filter(is_active=True)

class ShipmentBatchAdmin(admin.ModelAdmin):
    form = ShipmentBatchAdminForm
    list_display = ['batch_code', 'label', 'quantity', 'status', 'reviewer1', 'reviewer2']
    readonly_fields = ['status'] 

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        
        if change:
            obj.update_status_based_on_reviews()

admin.site.register(SKU, SKUAdmin)
admin.site.register(LabelVersion, LabelVersionAdmin)
admin.site.register(ShipmentBatch, ShipmentBatchAdmin)