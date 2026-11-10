import { Component, inject } from '@angular/core';

import { ThemeService } from '../../../core/services/theme.service';
import { IconComponent } from '../../../shared/icon/icon.component';

@Component({
  selector: 'app-auth-layout',
  imports: [IconComponent],
  templateUrl: './auth-layout.component.html',
  styleUrl: './auth-layout.component.scss',
})
export class AuthLayoutComponent {
  protected readonly theme = inject(ThemeService);
}
