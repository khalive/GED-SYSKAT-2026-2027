import { Component, inject } from '@angular/core';

import { NotificationService } from '../../core/services/notification.service';
import { IconComponent, IconName } from '../icon/icon.component';

@Component({
  selector: 'app-toasts',
  imports: [IconComponent],
  template: `
    <div class="pile" aria-live="polite" aria-atomic="false">
      @for (n of notifs.liste(); track n.id) {
        <div class="toast" [class]="'toast ' + n.type" role="status">
          <app-icon [name]="icone(n.type)" [size]="18" />
          <span>{{ n.message }}</span>
          <button type="button" class="btn btn-icon" (click)="notifs.fermer(n.id)" aria-label="Fermer">
            <app-icon name="x" [size]="16" />
          </button>
        </div>
      }
    </div>
  `,
  styles: `
    .pile { position: fixed; inset-block-end: 1rem; inset-inline-end: 1rem; z-index: 100;
      display: flex; flex-direction: column; gap: .6rem; width: min(380px, calc(100vw - 2rem)); }
    .toast { display: flex; align-items: center; gap: .65rem; padding: .75rem .85rem; border-radius: var(--r-sm);
      background: var(--surface); border: 1px solid var(--border); border-inline-start-width: 4px;
      box-shadow: var(--shadow-lg); animation: entree .22s ease-out; }
    .toast span { flex: 1; font-size: .92rem; }
    .succes { border-inline-start-color: var(--success); } .succes app-icon { color: var(--success); }
    .erreur { border-inline-start-color: var(--danger); } .erreur app-icon { color: var(--danger); }
    .avertissement { border-inline-start-color: var(--warning); } .avertissement app-icon { color: var(--warning); }
    .info { border-inline-start-color: var(--info); } .info app-icon { color: var(--info); }
    @keyframes entree { from { opacity: 0; transform: translateY(8px); } }
  `,
})
export class ToastsComponent {
  protected readonly notifs = inject(NotificationService);

  protected icone(type: string): IconName {
    return type === 'succes' ? 'check' : type === 'erreur' || type === 'avertissement' ? 'alert' : 'info';
  }
}
