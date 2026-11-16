import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import {
  PermissionMetier,
  RoleGestion,
  RoleWrite,
} from '../../core/models/accounts-admin.models';
import { NotificationService } from '../../core/services/notification.service';
import { RolesService } from '../../core/services/roles.service';
import { messageApi } from '../../core/utils/http-erreur';
import { IconComponent } from '../../shared/icon/icon.component';

@Component({
  selector: 'app-roles',
  imports: [ReactiveFormsModule, IconComponent],
  templateUrl: './roles.component.html',
  styleUrl: './roles.component.scss',
})
export class RolesComponent {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly service = inject(RolesService);
  private readonly notifications = inject(NotificationService);

  protected readonly roles = signal<RoleGestion[]>([]);
  protected readonly permissions = signal<PermissionMetier[]>([]);
  protected readonly roleEnCours = signal<number | null>(null);
  protected readonly permissionEnCours = signal<number | null>(null);
  protected readonly permissionsSelectionnees = signal<number[]>([]);
  protected readonly sauvegarde = signal(false);

  protected readonly roleForm = this.fb.group({
    code: ['', [Validators.required, Validators.maxLength(50)]],
    libelle: ['', [Validators.required, Validators.maxLength(100)]],
  });
  protected readonly permissionForm = this.fb.group({
    code: ['', [Validators.required, Validators.maxLength(100)]],
    ressource: ['', [Validators.required, Validators.maxLength(100)]],
    action: ['', [Validators.required, Validators.maxLength(50)]],
  });

  constructor() {
    this.charger();
  }

  protected charger(): void {
    this.service.roles().subscribe({
      next: (page) => this.roles.set(page.results),
      error: (err: HttpErrorResponse) =>
        this.notifications.erreur(messageApi(err, 'Impossible de charger les rôles.')),
    });
    this.service.permissions().subscribe({
      next: (page) => this.permissions.set(page.results),
      error: (err: HttpErrorResponse) =>
        this.notifications.erreur(messageApi(err, 'Impossible de charger les permissions.')),
    });
  }

  protected choisirRole(role: RoleGestion): void {
    this.roleEnCours.set(role.id);
    this.roleForm.setValue({ code: role.code, libelle: role.libelle });
    this.permissionsSelectionnees.set(role.permissions.map((permission) => permission.id));
  }

  protected nouveauRole(): void {
    this.roleEnCours.set(null);
    this.roleForm.reset({ code: '', libelle: '' });
    this.permissionsSelectionnees.set([]);
  }

  protected basculerPermission(id: number, event: Event): void {
    if (!(event.target instanceof HTMLInputElement)) return;
    const checked = event.target.checked;
    this.permissionsSelectionnees.update((ids) =>
      checked ? [...new Set([...ids, id])] : ids.filter((permissionId) => permissionId !== id),
    );
  }

  protected enregistrerRole(): void {
    if (this.roleForm.invalid) {
      this.roleForm.markAllAsTouched();
      return;
    }
    const data: RoleWrite = {
      ...this.roleForm.getRawValue(),
      permission_ids: this.permissionsSelectionnees(),
    };
    const id = this.roleEnCours();
    this.sauvegarde.set(true);
    const requete = id === null ? this.service.creerRole(data) : this.service.modifierRole(id, data);
    requete.subscribe({
      next: () => {
        this.sauvegarde.set(false);
        this.notifications.succes(id === null ? 'Rôle créé.' : 'Rôle mis à jour.');
        this.nouveauRole();
        this.charger();
      },
      error: (err: HttpErrorResponse) => {
        this.sauvegarde.set(false);
        this.notifications.erreur(messageApi(err, 'Impossible d’enregistrer le rôle.'));
      },
    });
  }

  protected supprimerRole(role: RoleGestion): void {
    if (!window.confirm(`Supprimer le rôle « ${role.libelle} » ?`)) return;
    this.service.supprimerRole(role.id).subscribe({
      next: () => {
        this.notifications.succes('Rôle supprimé.');
        if (this.roleEnCours() === role.id) this.nouveauRole();
        this.charger();
      },
      error: (err: HttpErrorResponse) =>
        this.notifications.erreur(messageApi(err, 'Impossible de supprimer ce rôle.')),
    });
  }

  protected creerPermission(): void {
    if (this.permissionForm.invalid) {
      this.permissionForm.markAllAsTouched();
      return;
    }
    const id = this.permissionEnCours();
    const requete = id === null
      ? this.service.creerPermission(this.permissionForm.getRawValue())
      : this.service.modifierPermission(id, this.permissionForm.getRawValue());
    requete.subscribe({
      next: () => {
        this.permissionEnCours.set(null);
        this.permissionForm.reset({ code: '', ressource: '', action: '' });
        this.notifications.succes(id === null ? 'Permission ajoutée au catalogue.' : 'Permission mise à jour.');
        this.charger();
      },
      error: (err: HttpErrorResponse) =>
        this.notifications.erreur(messageApi(err, 'Impossible de créer cette permission.')),
    });
  }

  protected choisirPermission(permission: PermissionMetier): void {
    this.permissionEnCours.set(permission.id);
    this.permissionForm.setValue({
      code: permission.code,
      ressource: permission.ressource,
      action: permission.action,
    });
  }

  protected annulerEditionPermission(): void {
    this.permissionEnCours.set(null);
    this.permissionForm.reset({ code: '', ressource: '', action: '' });
  }

  protected supprimerPermission(permission: PermissionMetier): void {
    if (!window.confirm(`Supprimer la permission « ${permission.code} » ?`)) return;
    this.service.supprimerPermission(permission.id).subscribe({
      next: () => {
        this.notifications.succes('Permission supprimée.');
        if (this.permissionEnCours() === permission.id) this.annulerEditionPermission();
        this.permissionsSelectionnees.update((ids) => ids.filter((id) => id !== permission.id));
        this.charger();
      },
      error: (err: HttpErrorResponse) =>
        this.notifications.erreur(messageApi(err, 'Impossible de supprimer cette permission.')),
    });
  }
}
