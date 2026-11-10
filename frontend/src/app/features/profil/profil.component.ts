import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { LIBELLES_TYPE, Langue } from '../../core/models/auth.models';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { appliquerErreursChamps, messageApi } from '../../core/utils/http-erreur';
import { correspondance } from '../../core/utils/validators';
import { IconComponent } from '../../shared/icon/icon.component';
import { PasswordFieldComponent } from '../../shared/password-field/password-field.component';

@Component({
  selector: 'app-profil',
  imports: [ReactiveFormsModule, PasswordFieldComponent, IconComponent],
  templateUrl: './profil.component.html',
  styleUrl: './profil.component.scss',
})
export class ProfilComponent {
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly auth = inject(AuthService);
  private readonly notif = inject(NotificationService);

  protected readonly user = this.auth.user;
  protected readonly enregistrement = signal(false);
  protected readonly changement = signal(false);

  protected readonly typeLibelle = computed(() => LIBELLES_TYPE[this.user()?.type_utilisateur ?? ''] ?? '');
  protected readonly initiales = computed(() => {
    const u = this.user();
    const nom = (u && `${u.first_name} ${u.last_name}`.trim()) || u?.username || '';
    return nom.split(/\s+/).filter(Boolean).slice(0, 2).map((m) => m[0].toUpperCase()).join('');
  });

  protected readonly formProfil = this.fb.group({
    first_name: [''],
    last_name: [''],
    telephone: ['', Validators.pattern(/^[+0-9 ()-]{0,20}$/)],
    langue: this.fb.control<Langue>('fr'),
  });

  protected readonly formMdp = this.fb.group(
    {
      ancien: ['', Validators.required],
      nouveau: ['', [Validators.required, Validators.minLength(8)]],
      confirmation: ['', Validators.required],
    },
    { validators: correspondance('nouveau', 'confirmation') },
  );

  constructor() {
    // Remplit le formulaire quand le profil est chargé (ou changé depuis l'en-tête).
    effect(() => {
      const u = this.user();
      if (u && this.formProfil.pristine) {
        this.formProfil.reset({
          first_name: u.first_name,
          last_name: u.last_name,
          telephone: u.telephone,
          langue: u.langue,
        });
      }
    });
  }

  enregistrerProfil(): void {
    if (this.formProfil.invalid) {
      this.formProfil.markAllAsTouched();
      return;
    }
    this.enregistrement.set(true);
    this.auth.modifierProfil(this.formProfil.getRawValue()).subscribe({
      next: () => {
        this.enregistrement.set(false);
        this.formProfil.markAsPristine();
        this.notif.succes('Profil mis à jour.');
      },
      error: (err: HttpErrorResponse) => {
        this.enregistrement.set(false);
        this.notif.erreur(messageApi(err, 'Impossible de mettre à jour le profil.'));
      },
    });
  }

  changerMotDePasse(): void {
    if (this.formMdp.invalid) {
      this.formMdp.markAllAsTouched();
      return;
    }
    this.changement.set(true);
    const { ancien, nouveau } = this.formMdp.getRawValue();
    this.auth
      .changerMotDePasse({ ancien_mot_de_passe: ancien, nouveau_mot_de_passe: nouveau })
      .subscribe({
        next: () => {
          this.changement.set(false);
          this.formMdp.reset();
          this.notif.succes('Mot de passe modifié.');
        },
        error: (err: HttpErrorResponse) => {
          this.changement.set(false);
          const place = appliquerErreursChamps(err, {
            ancien_mot_de_passe: this.formMdp.controls.ancien,
            nouveau_mot_de_passe: this.formMdp.controls.nouveau,
          });
          if (!place) this.notif.erreur(messageApi(err, 'Impossible de changer le mot de passe.'));
        },
      });
  }
}
