import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AnciensEtudiantsService } from '../../../core/services/anciens-etudiants.service';
import { appliquerErreursChamps, messageApi } from '../../../core/utils/http-erreur';
import { IconComponent } from '../../../shared/icon/icon.component';
import { PasswordFieldComponent } from '../../../shared/password-field/password-field.component';
import { AuthLayoutComponent } from '../../auth/auth-layout/auth-layout.component';

@Component({
  selector: 'app-inscription-ancien-etudiant',
  imports: [ReactiveFormsModule, RouterLink, IconComponent, PasswordFieldComponent, AuthLayoutComponent],
  templateUrl: './inscription-ancien-etudiant.component.html',
  styleUrl: './inscription-ancien-etudiant.component.scss',
})
export class InscriptionAncienEtudiantComponent {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly service = inject(AnciensEtudiantsService);

  protected readonly envoi = signal(false);
  protected readonly erreur = signal('');
  protected readonly confirmation = signal('');
  protected readonly anneeMax = new Date().getFullYear();

  protected readonly form = this.fb.group({
    first_name: ['', Validators.required],
    last_name: ['', Validators.required],
    username: ['', Validators.required],
    email: ['', [Validators.required, Validators.email]],
    telephone: [''],
    password: ['', [Validators.required, Validators.minLength(8)]],
    matricule: ['', Validators.required],
    cni: ['', Validators.required],
    date_naissance: ['', Validators.required],
    annee_promotion: this.fb.control(new Date().getFullYear(), [
      Validators.required,
      Validators.min(1950),
      Validators.max(this.anneeMax),
    ]),
    filiere: ['', Validators.required],
  });

  protected soumettre(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.envoi.set(true);
    this.erreur.set('');
    this.service.inscrire(this.form.getRawValue()).subscribe({
      next: (reponse) => {
        this.envoi.set(false);
        this.confirmation.set(reponse.detail);
      },
      error: (err: HttpErrorResponse) => {
        this.envoi.set(false);
        const controles = this.form.controls;
        appliquerErreursChamps(err, {
          first_name: controles.first_name,
          last_name: controles.last_name,
          username: controles.username,
          email: controles.email,
          telephone: controles.telephone,
          password: controles.password,
          matricule: controles.matricule,
          cni: controles.cni,
          date_naissance: controles.date_naissance,
          annee_promotion: controles.annee_promotion,
          filiere: controles.filiere,
        });
        this.erreur.set(messageApi(err, 'Impossible de transmettre la demande.'));
      },
    });
  }
}
