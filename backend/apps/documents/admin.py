from django.contrib import admin

from .models import ChampMetadonnee, Document, Dossier, Page, TypeDocument, VersionDocument


class ChampMetadonneeInline(admin.TabularInline):
    model = ChampMetadonnee
    extra = 1


@admin.register(TypeDocument)
class TypeDocumentAdmin(admin.ModelAdmin):
    list_display = ("code", "libelle", "libelle_ar", "confidentiel")
    filter_horizontal = ("roles_autorises",)
    inlines = [ChampMetadonneeInline]


@admin.register(Dossier)
class DossierAdmin(admin.ModelAdmin):
    list_display = ("cote", "intitule", "type_dossier", "matricule", "parent")
    list_filter = ("type_dossier", "classification")
    search_fields = ("cote", "intitule", "matricule")


class VersionInline(admin.TabularInline):
    model = VersionDocument
    extra = 0
    readonly_fields = ("empreinte_sha256", "date_creation")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("reference", "titre", "type_document", "annee_document", "statut")
    list_filter = ("statut", "type_document", "langue", "classification")
    search_fields = ("reference", "titre", "titre_ar")
    readonly_fields = ("empreinte_sha256", "date_creation")
    inlines = [VersionInline]


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("version", "numero", "confiance_ocr")
    search_fields = ("texte_ocr",)