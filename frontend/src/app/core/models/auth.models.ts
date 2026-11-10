export type Langue = 'fr' | 'ar';

export interface RoleSimple {
  id: number;
  code: string;
  libelle: string;
}

export interface ProfilEtudiant {
  matricule: string;
  cni: string;
  date_naissance: string;
  annee_promotion: number;
  filiere: string;
}

export interface Utilisateur {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  type_utilisateur: string;
  telephone: string;
  langue: Langue;
  roles: RoleSimple[];
  permissions: string[];
  profil_etudiant: ProfilEtudiant | null;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user: Utilisateur;
}

export interface RefreshResponse {
  access: string;
}

export interface ChangePasswordRequest {
  ancien_mot_de_passe: string;
  nouveau_mot_de_passe: string;
}

export interface MessageResponse {
  detail: string;
}

export interface PasswordResetConfirmRequest {
  uid: string;
  token: string;
  nouveau_mot_de_passe: string;
}

export interface ProfilUpdateRequest {
  first_name?: string;
  last_name?: string;
  telephone?: string;
  langue?: Langue;
}

export const LIBELLES_TYPE: Record<string, string> = {
  administrateur: 'Administrateur',
  archiviste: 'Archiviste',
  operateur: 'Opérateur de numérisation',
  controleur: 'Contrôleur qualité',
  auditeur: 'Auditeur',
  scolarite: 'Agent de scolarité',
  financier: 'Agent financier',
  direction: 'Direction',
  ancien_etudiant: 'Ancien étudiant',
  externe: 'Utilisateur externe',
};
