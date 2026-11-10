from django.contrib import admin

from .models import ControleQualite, LotNumerisation, TacheOCR


class ControleQualiteInline(admin.TabularInline):
    model = ControleQualite
    extra = 0


@admin.register(LotNumerisation)
class LotNumerisationAdmin(admin.ModelAdmin):
    list_display = ("numero_lot", "operateur", "statut", "nb_documents_prevus", "progression")
    list_filter = ("statut",)
    search_fields = ("numero_lot",)
    inlines = [ControleQualiteInline]

    @admin.display(description="Progression (%)")
    def progression(self, obj):
        return obj.calculer_progression()


@admin.register(ControleQualite)
class ControleQualiteAdmin(admin.ModelAdmin):
    list_display = ("lot", "controleur", "taux_conformite", "decision", "date_controle")
    list_filter = ("decision",)


@admin.register(TacheOCR)
class TacheOCRAdmin(admin.ModelAdmin):
    list_display = ("document", "langue", "statut", "confiance", "debut", "fin")
    list_filter = ("statut", "langue")