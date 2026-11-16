import { Langue, ProfilEtudiant, RoleSimple } from './auth.models';

export interface GestionUtilisateur {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  type_utilisateur: string;
  telephone: string;
  langue: Langue;
  is_active: boolean;
  roles: RoleSimple[];
  profil_etudiant: ProfilEtudiant | null;
  date_joined: string;
  last_login: string | null;
}

export interface UtilisateursPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: GestionUtilisateur[];
}

export interface EcritureUtilisateur {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  type_utilisateur: string;
  telephone: string;
  langue: Langue;
  is_active: boolean;
  role_ids: number[];
  password?: string;
}
