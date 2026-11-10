import { Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { LIBELLES_TYPE } from '../../core/models/auth.models';
import { AuthService } from '../../core/services/auth.service';
import { IconComponent } from '../../shared/icon/icon.component';

@Component({
  selector: 'app-accueil',
  imports: [RouterLink, IconComponent],
  templateUrl: './accueil.component.html',
  styleUrl: './accueil.component.scss',
})
export class AccueilComponent {
  protected readonly auth = inject(AuthService);

  protected readonly salutation = new Date().getHours() < 18 ? 'Bonjour' : 'Bonsoir';
  protected readonly dateDuJour = new Date().toLocaleDateString('fr-FR', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });

  protected readonly prenom = computed(() => {
    const u = this.auth.user();
    return u?.first_name || u?.username || '';
  });
  protected readonly typeLibelle = computed(
    () => LIBELLES_TYPE[this.auth.user()?.type_utilisateur ?? ''] ?? '',
  );
  protected readonly permissionsVisibles = computed(() => this.auth.user()?.permissions.slice(0, 8) ?? []);
  protected readonly permissionsRestantes = computed(
    () => Math.max(0, (this.auth.user()?.permissions.length ?? 0) - 8),
  );
}
