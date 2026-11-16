import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { LIBELLES_TYPE, Langue, RoleSimple } from '../../core/models/auth.models';
import { EcritureUtilisateur, GestionUtilisateur } from '../../core/models/utilisateurs.models';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { UtilisateursService } from '../../core/services/utilisateurs.service';
import { appliquerErreursChamps, messageApi } from '../../core/utils/http-erreur';
import { IconComponent } from '../../shared/icon/icon.component';

@Component({
  selector: 'app-utilisateurs',
  imports: [IconComponent, ReactiveFormsModule],
  templateUrl: './utilisateurs.component.html',
  styleUrl: './utilisateurs.component.scss',
})
export class UtilisateursComponent {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly auth = inject(AuthService);
  private readonly utilisateursService = inject(UtilisateursService);
  private readonly notifications = inject(NotificationService);

  protected readonly utilisateurs = signal<GestionUtilisateur[]>([]);
  protected readonly roles = signal<RoleSimple[]>([]);
  protected readonly recherche = signal('');
  protected readonly chargement = signal(false);
  protected readonly erreur = signal('');
  protected readonly page = signal(1);
  protected readonly total = signal(0);
  protected readonly pageSuivante = signal(false);
  protected readonly formulaireOuvert = signal(false);
  protected readonly utilisateurEdite = signal<GestionUtilisateur | null>(null);
  protected readonly sauvegarde = signal(false);
  protected readonly erreurFormulaire = signal('');
  protected readonly types = Object.entries(LIBELLES_TYPE).map(([code, libelle]) => ({ code, libelle }));

  protected readonly form = this.fb.group({
    username: ['', Validators.required],
    email: ['', [Validators.required, Validators.email]],
    first_name: [''],
    last_name: [''],
    type_utilisateur: ['externe', Validators.required],
    telephone: [''],
    langue: this.fb.control<Langue>('fr'),
    is_active: this.fb.control(false),
    role_ids: this.fb.control<number[]>([]),
    password: [''],
  });

  constructor() {
    this.charger();
    this.utilisateursService.rolesDisponibles().subscribe({
      next: (roles) => this.roles.set(roles),
      error: (err: HttpErrorResponse) =>
        this.notifications.erreur(messageApi(err, 'Impossible de charger les rôles disponibles.')),
    });
  }

  protected rechercher(valeur: string): void {
    this.recherche.set(valeur);
    this.page.set(1);
    this.charger();
  }

  protected changerPage(page: number): void {
    this.page.set(page);
    this.charger();
  }

  protected peutDesactiver(utilisateur: GestionUtilisateur): boolean {
    return utilisateur.is_active && utilisateur.id !== this.auth.user()?.id;
  }

  protected desactiver(utilisateur: GestionUtilisateur): void {
    if (!window.confirm(`Désactiver le compte de ${utilisateur.username} ?`)) return;
    this.utilisateursService.desactiver(utilisateur.id).subscribe({
      next: () => {
        this.notifications.succes('Compte désactivé. Il reste consultable et peut être réactivé.');
        this.charger();
      },
      error: (err: HttpErrorResponse) =>
        this.notifications.erreur(messageApi(err, 'Impossible de désactiver ce compte.')),
    });
  }

  protected ouvrirCreation(): void {
    this.utilisateurEdite.set(null);
    this.erreurFormulaire.set('');
    this.form.reset({
      username: '',
      email: '',
      first_name: '',
      last_name: '',
      type_utilisateur: 'externe',
      telephone: '',
      langue: 'fr',
      is_active: false,
      role_ids: [],
      password: '',
    });
    this.formulaireOuvert.set(true);
  }

  protected ouvrirEdition(utilisateur: GestionUtilisateur): void {
    this.utilisateurEdite.set(utilisateur);
    this.erreurFormulaire.set('');
    this.form.reset({
      username: utilisateur.username,
      email: utilisateur.email,
      first_name: utilisateur.first_name,
      last_name: utilisateur.last_name,
      type_utilisateur: utilisateur.type_utilisateur,
      telephone: utilisateur.telephone,
      langue: utilisateur.langue,
      is_active: utilisateur.is_active,
      role_ids: utilisateur.roles.map((role) => role.id),
      password: '',
    });
    this.formulaireOuvert.set(true);
  }

  protected basculerRole(id: number, event: Event): void {
    if (!(event.target instanceof HTMLInputElement)) return;
    const ids = this.form.controls.role_ids.value;
    this.form.controls.role_ids.setValue(
      event.target.checked ? [...new Set([...ids, id])] : ids.filter((roleId) => roleId !== id),
    );
  }

  protected enregistrer(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const valeur = this.form.getRawValue();
    const data: EcritureUtilisateur = {
      username: valeur.username,
      email: valeur.email,
      first_name: valeur.first_name,
      last_name: valeur.last_name,
      type_utilisateur: valeur.type_utilisateur,
      telephone: valeur.telephone,
      langue: valeur.langue,
      is_active: valeur.is_active,
      role_ids: valeur.role_ids,
      ...(valeur.password ? { password: valeur.password } : {}),
    };
    const edition = this.utilisateurEdite();
    if (!edition && !data.password) {
      this.form.controls.password.setErrors({ required: true });
      this.form.controls.password.markAsTouched();
      return;
    }

    this.sauvegarde.set(true);
    const requete = edition
      ? this.utilisateursService.modifier(edition.id, data)
      : this.utilisateursService.creer(data);
    requete.subscribe({
      next: () => {
        this.sauvegarde.set(false);
        this.formulaireOuvert.set(false);
        this.erreurFormulaire.set('');
        this.notifications.succes(edition ? 'Compte utilisateur mis à jour.' : 'Compte utilisateur créé.');
        this.charger();
      },
      error: (err: HttpErrorResponse) => {
        this.sauvegarde.set(false);
        const c = this.form.controls;
        const place = appliquerErreursChamps(err, {
          username: c.username,
          email: c.email,
          first_name: c.first_name,
          last_name: c.last_name,
          type_utilisateur: c.type_utilisateur,
          telephone: c.telephone,
          langue: c.langue,
          is_active: c.is_active,
          password: c.password,
        });
        this.erreurFormulaire.set(messageApi(err, 'Impossible d’enregistrer ce compte.'));
        if (!place) this.notifications.erreur(this.erreurFormulaire());
      },
    });
  }

  protected typeLibelle(type: string): string {
    return LIBELLES_TYPE[type] ?? type;
  }

  protected typesDisponibles(): { code: string; libelle: string }[] {
    const estAncienEtudiant = this.utilisateurEdite()?.type_utilisateur === 'ancien_etudiant';
    return this.types.filter((type) => type.code !== 'ancien_etudiant' || estAncienEtudiant);
  }

  private charger(): void {
    this.chargement.set(true);
    this.erreur.set('');
    this.utilisateursService
      .lister({
        page: this.page(),
        search: this.recherche().trim(),
        type_utilisateur: '',
        is_active: '',
      })
      .subscribe({
        next: (resultat) => {
          this.utilisateurs.set(resultat.results);
          this.total.set(resultat.count);
          this.pageSuivante.set(resultat.next !== null);
          this.chargement.set(false);
        },
        error: (err: HttpErrorResponse) => {
          this.erreur.set(
            err.status === 0
              ? 'Serveur injoignable. Vérifiez que le backend est démarré.'
              : 'Impossible de charger la liste des utilisateurs.',
          );
          this.chargement.set(false);
        },
      });
  }
}
