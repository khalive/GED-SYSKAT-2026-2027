from django.contrib import admin

from .models import (
    BordereauElimination,
    EmplacementPhysique,
    LigneBordereau,
    RegleConservation,
)


@admin.register(RegleConservation)
class RegleConservationAdmin(admin.ModelAdmin):
    list_display = ("type_document", "libelle", "duree_annees", "sort_final")
    list_filter = ("sort_final",)


@admin.register(EmplacementPhysique)
class EmplacementPhysiqueAdmin(admin.ModelAdmin):
    list_display = ("salle", "rayon", "boite", "etat")
    list_filter = ("etat", "salle")


class LigneBordereauInline(admin.TabularInline):
    model = LigneBordereau
    extra = 1
    autocomplete_fields = ("document",)


@admin.register(BordereauElimination)
class BordereauEliminationAdmin(admin.ModelAdmin):
    list_display = ("numero", "date_creation", "statut", "etabli_par")
    list_filter = ("statut",)
    inlines = [LigneBordereauInline]


@admin.register(LigneBordereau)
class LigneBordereauAdmin(admin.ModelAdmin):
    list_display = ("bordereau", "document")