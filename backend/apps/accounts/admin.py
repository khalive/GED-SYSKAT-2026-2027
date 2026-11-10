from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AncienEtudiant, JournalAudit, Permission, Role, Utilisateur

@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = ("username", "email", "type_utilisateur", "is_active")
    list_filter = ("type_utilisateur", "is_active", "roles")
    fieldsets = UserAdmin.fieldsets + (
        ("Profil GED", {"fields": ("type_utilisateur", "telephone", "langue", "roles")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Profil GED", {"fields": ("email", "type_utilisateur", "telephone", "langue")}),
    )
    filter_horizontal = UserAdmin.filter_horizontal + ("roles",)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "libelle")
    filter_horizontal = ("permissions",)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "ressource", "action")
    search_fields = ("code", "ressource")


@admin.register(AncienEtudiant)
class AncienEtudiantAdmin(admin.ModelAdmin):
    list_display = ("matricule", "utilisateur", "filiere", "annee_promotion")
    search_fields = ("matricule", "cni", "utilisateur__username")


@admin.register(JournalAudit)
class JournalAuditAdmin(admin.ModelAdmin):
    list_display = ("date_action", "utilisateur", "action", "entite_cible", "adresse_ip")
    list_filter = ("action",)
    readonly_fields = [f.name for f in JournalAudit._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False