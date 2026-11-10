import { ChangeDetectionStrategy, Component, input, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';

import { ForceMotDePasse, forceMotDePasse } from '../../core/utils/mot-de-passe';
import { IconComponent } from '../icon/icon.component';

@Component({
  selector: 'app-password-field',
  imports: [ReactiveFormsModule, IconComponent],
  changeDetection: ChangeDetectionStrategy.Default,
  template: `
    <div class="field">
      <label [for]="id()">{{ label() }}</label>
      <div class="input-wrap">
        <app-icon class="lead" name="lock" [size]="18" />
        <input
          [id]="id()"
          [type]="visible() ? 'text' : 'password'"
          [formControl]="control()"
          [attr.autocomplete]="autocomplete()"
          [attr.aria-invalid]="control().touched && control().invalid"
        />
        <button
          type="button" class="btn btn-icon toggle"
          (click)="visible.set(!visible())"
          [attr.aria-label]="visible() ? 'Masquer le mot de passe' : 'Afficher le mot de passe'"
        >
          <app-icon [name]="visible() ? 'eye-off' : 'eye'" [size]="18" />
        </button>
      </div>

      @if (force() && control().value) {
        <div class="force" [attr.data-niveau]="evaluation().niveau" aria-live="polite">
          <span class="barres"><i></i><i></i><i></i><i></i></span>
          <small>{{ evaluation().libelle }}</small>
        </div>
      }

      @if (control().touched && control().invalid) {
        <small class="erreur-champ" role="alert">
          @if (control().errors?.['serveur']) {
            {{ control().errors?.['serveur'] }}
          } @else if (control().errors?.['required']) {
            Ce champ est obligatoire.
          } @else if (control().errors?.['minlength']) {
            8 caractères minimum.
          }
        </small>
      }
    </div>
  `,
  styles: `
    .force { display: flex; align-items: center; gap: .6rem; margin-top: .5rem; }
    .barres { display: flex; gap: 4px; flex: 1; }
    .barres i { height: 5px; flex: 1; border-radius: 99px; background: var(--border); transition: background .2s; }
    small { color: var(--muted); font-size: .8rem; min-width: 5.5rem; text-align: end; }
    [data-niveau='1'] .barres i:nth-child(-n + 1) { background: var(--danger); }
    [data-niveau='2'] .barres i:nth-child(-n + 2) { background: var(--warning); }
    [data-niveau='3'] .barres i:nth-child(-n + 3) { background: var(--accent); }
    [data-niveau='4'] .barres i:nth-child(-n + 4) { background: var(--success); }
  `,
})
export class PasswordFieldComponent {
  readonly control = input.required<FormControl<string>>();
  readonly label = input.required<string>();
  readonly id = input.required<string>();
  readonly autocomplete = input('current-password');
  readonly force = input(false);

  protected readonly visible = signal(false);

  protected evaluation(): ForceMotDePasse {
    return forceMotDePasse(this.control().value);
  }
}
