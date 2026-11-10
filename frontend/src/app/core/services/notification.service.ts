import { Injectable, computed, signal } from '@angular/core';

export type TypeNotification = 'succes' | 'erreur' | 'avertissement' | 'info';

export interface Notification {
  id: number;
  type: TypeNotification;
  message: string;
  date: Date;
  lue: boolean;
}

/**
 * Messages de l'interface : toasts éphémères + historique de la session (cloche).
 * Les notifications serveur (app `core`) seront branchées dans une étape ultérieure.
 */
@Injectable({ providedIn: 'root' })
export class NotificationService {
  /** Toasts actuellement affichés. */
  private readonly _liste = signal<Notification[]>([]);
  readonly liste = this._liste.asReadonly();

  /** Historique de la session (20 derniers messages). */
  private readonly _historique = signal<Notification[]>([]);
  readonly historique = this._historique.asReadonly();
  readonly nonLues = computed(() => this._historique().filter((n) => !n.lue).length);

  private suivant = 0;

  afficher(type: TypeNotification, message: string, duree = 5000): void {
    const notif: Notification = { id: ++this.suivant, type, message, date: new Date(), lue: false };
    this._liste.update((l) => [...l, notif]);
    this._historique.update((h) => [notif, ...h].slice(0, 20));
    window.setTimeout(() => this.fermer(notif.id), duree);
  }

  succes(message: string): void { this.afficher('succes', message); }
  erreur(message: string): void { this.afficher('erreur', message, 7000); }
  avertissement(message: string): void { this.afficher('avertissement', message); }
  info(message: string): void { this.afficher('info', message); }

  fermer(id: number): void {
    this._liste.update((l) => l.filter((n) => n.id !== id));
  }

  marquerToutesLues(): void {
    this._historique.update((h) => h.map((n) => ({ ...n, lue: true })));
  }

  viderHistorique(): void {
    this._historique.set([]);
  }
}
