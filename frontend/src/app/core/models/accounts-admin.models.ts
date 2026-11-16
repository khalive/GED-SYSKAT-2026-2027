export interface PermissionMetier {
  id: number;
  code: string;
  ressource: string;
  action: string;
}

export interface RoleGestion {
  id: number;
  code: string;
  libelle: string;
  permissions: PermissionMetier[];
}

export interface RoleWrite {
  code: string;
  libelle: string;
  permission_ids: number[];
}

export interface PermissionWrite {
  code: string;
  ressource: string;
  action: string;
}

export interface PageApi<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface LigneAudit {
  id: number;
  date_action: string;
  action: string;
  entite_cible: string;
  id_cible: number | null;
  adresse_ip: string | null;
  details: Record<string, unknown>;
  utilisateur_id: number | null;
  utilisateur_username: string | null;
}

export interface FiltresAudit {
  page: number;
  search: string;
  action: string;
  depuis: string;
  jusqua: string;
}

export interface InscriptionAncienEtudiant {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  telephone: string;
  password: string;
  matricule: string;
  cni: string;
  date_naissance: string;
  annee_promotion: number;
  filiere: string;
}

export interface ProfilAncienEtudiant {
  matricule: string;
  cni: string;
  date_naissance: string;
  annee_promotion: number;
  filiere: string;
}

