import { Routes } from '@angular/router';

import { authGuard, guestGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    title: 'Connexion · GED ENG',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/auth/login/login.component').then((m) => m.LoginComponent),
  },
  {
    path: 'mot-de-passe-oublie',
    title: 'Mot de passe oublié · GED ENG',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/auth/forgot-password/forgot-password.component').then((m) => m.ForgotPasswordComponent),
  },
  {
    // Pas de guest guard : le lien de l'e-mail doit fonctionner même si une session est ouverte.
    path: 'reinitialiser-mot-de-passe',
    title: 'Nouveau mot de passe · GED ENG',
    loadComponent: () =>
      import('./features/auth/reset-password/reset-password.component').then((m) => m.ResetPasswordComponent),
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./core/layout/shell/shell.component').then((m) => m.ShellComponent),
    children: [
      {
        path: 'accueil',
        title: 'Accueil · GED ENG',
        loadComponent: () => import('./features/accueil/accueil.component').then((m) => m.AccueilComponent),
      },
      {
        path: 'profil',
        title: 'Mon profil · GED ENG',
        loadComponent: () => import('./features/profil/profil.component').then((m) => m.ProfilComponent),
      },
      { path: '', pathMatch: 'full', redirectTo: 'accueil' },
    ],
  },
  { path: '**', redirectTo: 'accueil' },
];
