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

/** Réserve la gestion des comptes aux titulaires de la permission adaptée. */
export const administrationGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const user = auth.user();
  return auth.hasPermission('utilisateurs.gerer')
    || Boolean(user?.is_staff && user.roles.length === 0)
    ? true
    : router.createUrlTree(['/accueil']);
};

/** L'auditeur consulte le journal sans pouvoir gérer les comptes. */
export const auditGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const user = auth.user();
  return auth.hasPermission('audit.consulter')
    || Boolean(user?.is_staff && user.roles.length === 0)
    ? true
    : router.createUrlTree(['/accueil']);
};

export const staffGuard = administrationGuard;

/** Réserve le profil étudiant aux comptes vérifiés d'anciens étudiants. */
export const ancienEtudiantGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth.user()?.type_utilisateur === 'ancien_etudiant'
    ? true
    : router.createUrlTree(['/accueil']);
};
