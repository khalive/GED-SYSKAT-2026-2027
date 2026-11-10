import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { AuthService } from '../../../core/services/auth.service';
import { appliquerErreursChamps, messageApi } from '../../../core/utils/http-erreur';
import { correspondance } from '../../../core/utils/validators';
import { IconComponent } from '../../../shared/icon/icon.component';
import { PasswordFieldComponent } from '../../../shared/password-field/password-field.component';
import { AuthLayoutComponent } from '../auth-layout/auth-layout.component';

type Etat = 'formulaire' | 'succes' | 'invalide';

@Component({
  selector: 'app-reset-password',
  imports: [ReactiveFormsModule, RouterLink, AuthLayoutComponent, PasswordFieldComponent, IconComponent],
  templateUrl: './reset-password.component.html',
})
export class ResetPasswordComponent {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);

  private readonly uid = this.route.snapshot.queryParamMap.get('uid') ?? '';
  private readonly token = this.route.snapshot.queryParamMap.get('token') ?? '';

  protected readonly etat = signal<Etat>(this.uid && this.token ? 'formulaire' : 'invalide');
  protected readonly chargement = signal(false);
  protected readonly erreur = signal<string | null>(null);

  protected readonly form = this.fb.group(
    {
      nouveau: ['', [Validators.required, Validators.minLength(8)]],
      confirmation: ['', Validators.required],
    },
    { validators: correspondance('nouveau', 'confirmation') },
  );

  soumettre(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.chargement.set(true);
    this.erreur.set(null);

    this.auth
      .confirmerReinitialisation({
        uid: this.uid,
        token: this.token,
        nouveau_mot_de_passe: this.form.controls.nouveau.value,
      })
      .subscribe({
        next: () => {
          this.chargement.set(false);
          this.etat.set('succes');
        },
        error: (err: HttpErrorResponse) => {
          this.chargement.set(false);
          // Lien expiré, déjà utilisé ou falsifié : inutile de laisser saisir un mot de passe.
          if (err.status === 400 && err.error?.token) {
            this.etat.set('invalide');
            return;
          }
          const place = appliquerErreursChamps(err, {
            nouveau_mot_de_passe: this.form.controls.nouveau,
          });
          if (!place) {
            this.erreur.set(messageApi(err, 'Impossible de modifier le mot de passe. Réessayez.'));
          }
        },
      });
  }
}
