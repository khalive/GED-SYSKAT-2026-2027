import { Component, HostListener, computed, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { LIBELLES_TYPE, Langue } from '../../models/auth.models';
import { AuthService } from '../../services/auth.service';
import { NotificationService } from '../../services/notification.service';
import { ThemeService } from '../../services/theme.service';
import { messageApi } from '../../utils/http-erreur';
import { IconComponent, IconName } from '../../../shared/icon/icon.component';

const CLE_SIDEBAR = 'ged.sidebar';

@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, IconComponent],
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss',
})
export class ShellComponent {
  protected readonly auth = inject(AuthService);
  protected readonly theme = inject(ThemeService);
  protected readonly notifs = inject(NotificationService);
  private readonly router = inject(Router);

  protected readonly reduit = signal(this.lireReduit());
  protected readonly mobileOuvert = signal(false);
  protected readonly menu = signal<'notif' | 'user' | null>(null);
  protected readonly annee = new Date().getFullYear();

  /** Modules prévus : affichés pour montrer la feuille de route, non cliquables. */
  protected readonly bientot: { label: string; icone: IconName }[] = [
    { label: 'Documents', icone: 'file' },
    { label: 'Numérisation', icone: 'scan' },
    { label: 'Demandes', icone: 'inbox' },
    { label: 'Conservation', icone: 'archive' },
  ];

  protected readonly nomAffiche = computed(() => {
    const u = this.auth.user();
    return (u && `${u.first_name} ${u.last_name}`.trim()) || u?.username || '';
  });

  protected readonly initiales = computed(() =>
    this.nomAffiche()
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((m) => m[0].toUpperCase())
      .join(''),
  );

  protected readonly typeLibelle = computed(() => {
    const t = this.auth.user()?.type_utilisateur ?? '';
    return LIBELLES_TYPE[t] ?? t;
  });

  @HostListener('document:click')
  @HostListener('document:keydown.escape')
  protected fermerMenus(): void {
    this.menu.set(null);
  }

  protected basculerMenu(nom: 'notif' | 'user', evt: Event): void {
    evt.stopPropagation();
    this.menu.update((m) => (m === nom ? null : nom));
  }

  protected basculerReduit(): void {
    const valeur = !this.reduit();
    this.reduit.set(valeur);
    try {
      localStorage.setItem(CLE_SIDEBAR, valeur ? '1' : '0');
    } catch {
      /* ignoré */
    }
  }

  protected changerLangue(langue: Langue): void {
    if (this.auth.user()?.langue === langue) return;
    this.auth.changerLangue(langue).subscribe({
      error: (err) => this.notifs.erreur(messageApi(err, 'Impossible de changer la langue.')),
    });
  }

  protected allerAuProfil(): void {
    this.router.navigate(['/profil']);
  }

  private lireReduit(): boolean {
    try {
      return localStorage.getItem(CLE_SIDEBAR) === '1';
    } catch {
      return false;
    }
  }
}
