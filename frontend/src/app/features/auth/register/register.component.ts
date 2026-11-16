import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../../core/services/auth.service';
import { appliquerErreursChamps, messageApi } from '../../../core/utils/http-erreur';
import { correspondance } from '../../../core/utils/validators';
import { IconComponent } from '../../../shared/icon/icon.component';
import { PasswordFieldComponent } from '../../../shared/password-field/password-field.component';
import { AuthLayoutComponent } from '../auth-layout/auth-layout.component';

@Component({
  selector: 'app-register',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    IconComponent,
    PasswordFieldComponent,
    AuthLayoutComponent,
  ],
  templateUrl: './register.component.html',
  styleUrl: './register.component.scss',
})
export class RegisterComponent {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly auth = inject(AuthService);

  protected readonly envoi = signal(false);
  protected readonly erreur = signal<string | null>(null);
  protected readonly confirmation = signal<string | null>(null);

  protected readonly form = this.fb.group(
    {
      first_name: ['', Validators.required],
      last_name: ['', Validators.required],
      username: ['', Validators.required],
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(8)]],
      mot_de_passe_confirmation: ['', Validators.required],
    },
    { validators: correspondance('password', 'mot_de_passe_confirmation') },
  );

  soumettre(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.envoi.set(true);
    this.erreur.set(null);
    const { first_name, last_name, username, email, password } = this.form.getRawValue();

    this.auth.inscrire({ first_name, last_name, username, email, password }).subscribe({
      next: (reponse) => {
        this.envoi.set(false);
        this.confirmation.set(reponse.detail);
      },
      error: (err: HttpErrorResponse) => {
        this.envoi.set(false);
        const champs = appliquerErreursChamps(err, {
          first_name: this.form.controls.first_name,
          last_name: this.form.controls.last_name,
          username: this.form.controls.username,
          email: this.form.controls.email,
          password: this.form.controls.password,
        });
        if (!champs) {
          this.erreur.set(messageApi(err, 'Impossible de transmettre la demande. Réessayez.'));
        }
      },
    });
  }
}
