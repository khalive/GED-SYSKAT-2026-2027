import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from '../services/auth.service';

/** Réserve une page aux utilisateurs connectés. */
export const authGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
const router = inject(Router);
return auth.isAuthenticated()
? true
: router.createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
};

/** Empêche un utilisateur déjà connecté de revoir l'écran de connexion. */
export const guestGuard: CanActivateFn = () => {
const auth = inject(AuthService);
const router = inject(Router);
return auth.isAuthenticated() ? router.createUrlTree(['/accueil']) : true;
};
