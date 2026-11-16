import { HttpErrorResponse } from '@angular/common/http';
import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';

import { AuthService } from '../../core/services/auth.service';
import { LigneAudit } from '../../core/models/accounts-admin.models';
import { AuditService } from '../../core/services/audit.service';
import { NotificationService } from '../../core/services/notification.service';
import { messageApi } from '../../core/utils/http-erreur';
import { IconComponent } from '../../shared/icon/icon.component';

@Component({
  selector: 'app-audit',
  imports: [DatePipe, IconComponent],
  templateUrl: './audit.component.html',
  styleUrl: './audit.component.scss',
})
export class AuditComponent {
  private readonly service = inject(AuditService);
  private readonly notifications = inject(NotificationService);
  protected readonly auth = inject(AuthService);

  protected readonly lignes = signal<LigneAudit[]>([]);
  protected readonly page = signal(1);
  protected readonly total = signal(0);
  protected readonly pageSuivante = signal(false);
  protected readonly chargement = signal(false);
  protected readonly recherche = signal('');
  protected readonly action = signal('');
  protected readonly depuis = signal('');
  protected readonly jusqua = signal('');

  protected readonly actions = [
    { code: 'connexion', libelle: 'Connexion' },
    { code: 'deconnexion', libelle: 'Déconnexion' },
    { code: 'consultation', libelle: 'Consultation' },
    { code: 'creation', libelle: 'Création' },
    { code: 'modification', libelle: 'Modification' },
    { code: 'suppression', libelle: 'Suppression' },
    { code: 'telechargement', libelle: 'Téléchargement' },
    { code: 'validation', libelle: 'Validation' },
    { code: 'export', libelle: 'Export' },
  ];

  constructor() {
    this.charger();
  }

  protected lireChamp(cible: EventTarget | null): string {
    return cible instanceof HTMLInputElement || cible instanceof HTMLSelectElement ? cible.value : '';
  }

  protected appliquerFiltres(): void {
    this.page.set(1);
    this.charger();
  }

  protected changerPage(page: number): void {
    this.page.set(page);
    this.charger();
  }

  protected libelleAction(code: string): string {
    return this.actions.find((action) => action.code === code)?.libelle ?? code;
  }

  protected details(ligne: LigneAudit): string {
    return JSON.stringify(ligne.details);
  }

  protected hasDetails(ligne: LigneAudit): boolean {
    return Object.keys(ligne.details).length > 0;
  }

  protected exporter(): void {
    this.service.exporter({
      page: this.page(),
      search: this.recherche().trim(),
      action: this.action(),
      depuis: this.dateIso(this.depuis(), false),
      jusqua: this.dateIso(this.jusqua(), true),
    }).subscribe({
      next: (fichier) => {
        const url = URL.createObjectURL(fichier);
        const lien = document.createElement('a');
        lien.href = url;
        lien.download = 'journal-audit.csv';
        document.body.appendChild(lien);
        lien.click();
        lien.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      },
      error: (err: HttpErrorResponse) =>
        this.notifications.erreur(messageApi(err, 'Impossible d’exporter le journal d’audit.')),
    });
  }

  private dateIso(value: string, fin: boolean): string {
    if (!value) return '';
    const date = new Date(`${value}T${fin ? '23:59:59.999' : '00:00:00'}`);
    return date.toISOString();
  }

  private charger(): void {
    this.chargement.set(true);
    this.service
      .lister({
        page: this.page(),
        search: this.recherche().trim(),
        action: this.action(),
        depuis: this.dateIso(this.depuis(), false),
        jusqua: this.dateIso(this.jusqua(), true),
      })
      .subscribe({
        next: (resultat) => {
          this.lignes.set(resultat.results);
          this.total.set(resultat.count);
          this.pageSuivante.set(resultat.next !== null);
          this.chargement.set(false);
        },
        error: (err: HttpErrorResponse) => {
          this.chargement.set(false);
          this.notifications.erreur(messageApi(err, 'Impossible de charger le journal d’audit.'));
        },
      });
  }
}
