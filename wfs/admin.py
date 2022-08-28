from django.contrib import admin
from wfs.models import Service, FeatureType, MetadataURL, BoundingBox,\
    ResolutionFilter
from django import forms


class MetadataURLInline(admin.StackedInline):
    model = MetadataURL
    extra = 0


class BBoxInline(admin.StackedInline):
    model = BoundingBox
    extra = 0


class ResolutionFilterInline(admin.StackedInline):
    model = ResolutionFilter
    extra = 0


class FeatureTypeForm(forms.ModelForm):
    fields = forms.MultipleChoiceField(required=False, choices=(), widget=forms.CheckboxSelectMultiple, help_text="Must contain a geometry field. Fields only appear for selection after you select a model. If no field is selected ALL fields will be displayed.")

    def __init__(self, *args, **kwargs):
        super(FeatureTypeForm, self).__init__(*args, **kwargs)
        if hasattr(self.instance, "model"):
            
            if self.instance.model is not None:
            
                model_fields = self.instance.model.model_class()._meta.get_fields()
                self.fields['fields'].choices = [(field.name, field.name) for field in model_fields]
                if self.instance.fields:
                    self.initial['fields'] = [str(field) for field in self.instance.fields.split(",")]

    class Meta:
        model = FeatureType
        exclude = ()

    def clean_fields(self):
        data = self.cleaned_data['fields']
        cleaned_data = ",".join(data)
        return cleaned_data


class FeatureTypeAdmin(admin.ModelAdmin):
    model = FeatureType
    form = FeatureTypeForm
    inlines = [ResolutionFilterInline, BBoxInline, MetadataURLInline]


admin.site.register(Service)
admin.site.register(FeatureType, FeatureTypeAdmin)
