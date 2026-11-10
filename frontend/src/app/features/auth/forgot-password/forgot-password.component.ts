import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../../core/services/auth.service';
import { messageApi } from '../../../core/utils/http-erreur';
import { IconComponent } from '../../../shared/icon/icon.component';
import { AuthLayoutComponent } from '../auth-layout/auth-layout.component';

@Component({
  selector: 'app-forgot-password',
  imports: [ReactiveFormsModule, RouterLink, AuthLayoutComponent, IconComponent],
  templateUrl: './forgot-password.component.html',
})
export class ForgotPasswordComponent {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly etat = signal<'saisie' | 'envoye'>('saisie');
  protected readonly chargement = signal(false);
  protected readonly erreur = signal<string | null>(null);
  protected readonly attente = signal(0);
  private minuteur?: number;

  protected readonly form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
  });

  constructor() {
    this.destroyRef.onDestroy(() => window.clearInterval(this.minuteur));
  }

  soumettre(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.chargement.set(true);
    this.erreur.set(null);

    this.auth.demanderReinitialisation(this.form.getRawValue().email.trim()).subscribe({
      next: () => {
        this.chargement.set(false);
        this.etat.set('envoye');
        this.demarrerAttente();
      },
      error: (err: HttpErrorResponse) => {
        this.chargement.set(false);
        this.erreur.set(messageApi(err, "Impossible d'envoyer la demande. Réessayez."));
      },
    });
  }

  protected modifierAdresse(): void {
    this.etat.set('saisie');
  }

  /** Empêche de renvoyer la demande pendant 30 secondes. */
  private demarrerAttente(): void {
    window.clearInterval(this.minuteur);
    this.attente.set(30);
    this.minuteur = window.setInterval(() => {
      this.attente.update((v) => Math.max(0, v - 1));
      if (this.attente() === 0) window.clearInterval(this.minuteur);
    }, 1000);
  }
}
