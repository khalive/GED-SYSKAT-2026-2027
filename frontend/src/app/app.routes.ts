import { Routes } from '@angular/router';

import {
  administrationGuard,
  ancienEtudiantGuard,
  auditGuard,
  authGuard,
  guestGuard,
} from './core/guards/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    title: 'Connexion · GED ENG',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/auth/login/login.component').then((m) => m.LoginComponent),
  },
  {
    path: 'inscription',
    title: 'Créer un compte · GED ENG',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/auth/register/register.component').then((m) => m.RegisterComponent),
  },
  {
    path: 'inscription-ancien-etudiant',
    title: 'Inscription alumni · GED ENG',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/anciens-etudiants/inscription/inscription-ancien-etudiant.component').then(
        (m) => m.InscriptionAncienEtudiantComponent,
      ),
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
      {
        path: 'utilisateurs',
        title: 'Utilisateurs · GED ENG',
        canActivate: [administrationGuard],
        loadComponent: () =>
          import('./features/utilisateurs/utilisateurs.component').then((m) => m.UtilisateursComponent),
      },
      {
        path: 'roles',
        title: 'Rôles et permissions · GED ENG',
        canActivate: [administrationGuard],
        loadComponent: () => import('./features/roles/roles.component').then((m) => m.RolesComponent),
      },
      {
        path: 'audit',
        title: 'Journal d’audit · GED ENG',
        canActivate: [auditGuard],
        loadComponent: () => import('./features/audit/audit.component').then((m) => m.AuditComponent),
      },
      {
        path: 'profil-etudiant',
        title: 'Mon parcours étudiant · GED ENG',
        canActivate: [ancienEtudiantGuard],
        loadComponent: () =>
          import('./features/anciens-etudiants/profil/profil-ancien-etudiant.component').then(
            (m) => m.ProfilAncienEtudiantComponent,
          ),
      },
      { path: '', pathMatch: 'full', redirectTo: 'accueil' },
    ],
  },
  { path: '**', redirectTo: 'accueil' },
];
