import { Injectable, signal } from '@angular/core';

export type Theme = 'light' | 'dark';
const CLE = 'ged.theme';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly _theme = signal<Theme>(this.lire());
  readonly theme = this._theme.asReadonly();

  constructor() {
    this.appliquer(this._theme());
  }

  basculer(): void {
    this.definir(this._theme() === 'light' ? 'dark' : 'light');
  }

  definir(theme: Theme): void {
    this._theme.set(theme);
    try {
      localStorage.setItem(CLE, theme);
    } catch {
      /* stockage indisponible : le thème reste appliqué pour la session */
    }
    this.appliquer(theme);
  }

  private lire(): Theme {
    try {
      const stocke = localStorage.getItem(CLE);
      if (stocke === 'light' || stocke === 'dark') return stocke;
    } catch {
      /* ignoré */
    }
    return 'light';
  }

  private appliquer(theme: Theme): void {
    document.documentElement.dataset['theme'] = theme;
  }
}
