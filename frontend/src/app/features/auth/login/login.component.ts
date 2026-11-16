import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { AuthService } from '../../../core/services/auth.service';
import { IconComponent } from '../../../shared/icon/icon.component';
import { PasswordFieldComponent } from '../../../shared/password-field/password-field.component';
import { AuthLayoutComponent } from '../auth-layout/auth-layout.component';

@Component({
  selector: 'app-login',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    IconComponent,
    PasswordFieldComponent,
    AuthLayoutComponent,
  ],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss',
})
export class LoginComponent {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  protected readonly chargement = signal(false);
  protected readonly erreur = signal<string | null>(null);

  protected readonly form = this.fb.group({
    username: ['', Validators.required],
    password: ['', Validators.required],
  });

  soumettre(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.chargement.set(true);
    this.erreur.set(null);

    this.auth.login(this.form.getRawValue()).subscribe({
      next: () => {
        const retour = this.route.snapshot.queryParamMap.get('returnUrl');
        this.router.navigateByUrl(retour && retour.startsWith('/') ? retour : '/accueil');
      },
      error: (err: HttpErrorResponse) => {
        this.chargement.set(false);
        this.erreur.set(this.messageErreur(err));
      },
    });
  }

  private messageErreur(err: HttpErrorResponse): string {
    switch (err.status) {
      case 401:
        return 'Identifiant ou mot de passe incorrect.';
      case 429:
        return 'Trop de tentatives. Réessayez dans une minute.';
      case 0:
        return 'Serveur injoignable. Vérifiez que le backend est démarré.';
      default:
        return 'Une erreur est survenue. Réessayez.';
    }
  }
}
