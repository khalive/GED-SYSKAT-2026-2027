import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { AnciensEtudiantsService } from '../../../core/services/anciens-etudiants.service';
import { NotificationService } from '../../../core/services/notification.service';
import { messageApi } from '../../../core/utils/http-erreur';
import { IconComponent } from '../../../shared/icon/icon.component';

@Component({
  selector: 'app-profil-ancien-etudiant',
  imports: [ReactiveFormsModule, IconComponent],
  templateUrl: './profil-ancien-etudiant.component.html',
  styleUrl: './profil-ancien-etudiant.component.scss',
})
export class ProfilAncienEtudiantComponent {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly service = inject(AnciensEtudiantsService);
  private readonly notifications = inject(NotificationService);

  protected readonly chargement = signal(true);
  protected readonly sauvegarde = signal(false);
  protected readonly erreur = signal('');
  protected readonly anneeMax = new Date().getFullYear();

  protected readonly form = this.fb.group({
    matricule: ['', Validators.required],
    cni: ['', Validators.required],
    date_naissance: ['', Validators.required],
    annee_promotion: this.fb.control(2000, [
      Validators.required,
      Validators.min(1950),
      Validators.max(this.anneeMax),
    ]),
    filiere: ['', Validators.required],
  });

  constructor() {
    this.service.monProfil().subscribe({
      next: (profil) => {
        this.form.setValue(profil);
        this.form.markAsPristine();
        this.chargement.set(false);
      },
      error: (err: HttpErrorResponse) => {
        this.erreur.set(messageApi(err, 'Impossible de charger votre profil étudiant.'));
        this.chargement.set(false);
      },
    });
  }

  protected enregistrer(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.sauvegarde.set(true);
    this.erreur.set('');
    this.service.modifierMonProfil(this.form.getRawValue()).subscribe({
      next: (profil) => {
        this.form.setValue(profil);
        this.form.markAsPristine();
        this.sauvegarde.set(false);
        this.notifications.succes('Votre profil étudiant a été mis à jour.');
      },
      error: (err: HttpErrorResponse) => {
        this.sauvegarde.set(false);
        this.erreur.set(messageApi(err, 'Impossible de mettre à jour votre profil.'));
      },
    });
  }
}
