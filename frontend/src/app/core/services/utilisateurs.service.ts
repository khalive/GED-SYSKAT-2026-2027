import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { RoleSimple } from '../models/auth.models';
import {
  EcritureUtilisateur,
  GestionUtilisateur,
  UtilisateursPage,
} from '../models/utilisateurs.models';

export interface FiltresUtilisateurs {
  page: number;
  search: string;
  type_utilisateur: string;
  is_active: string;
}

@Injectable({ providedIn: 'root' })
export class UtilisateursService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/utilisateurs`;

  lister(filtres: FiltresUtilisateurs): Observable<UtilisateursPage> {
    let params = new HttpParams().set('page', filtres.page);
    if (filtres.search) params = params.set('search', filtres.search);
    if (filtres.type_utilisateur) {
      params = params.set('type_utilisateur', filtres.type_utilisateur);
    }
    if (filtres.is_active) params = params.set('is_active', filtres.is_active);
    return this.http.get<UtilisateursPage>(`${this.base}/`, { params });
  }

  rolesDisponibles(): Observable<RoleSimple[]> {
    return this.http.get<RoleSimple[]>(`${this.base}/roles/`);
  }

  creer(data: EcritureUtilisateur): Observable<GestionUtilisateur> {
    return this.http.post<GestionUtilisateur>(`${this.base}/`, data);
  }

  modifier(id: number, data: EcritureUtilisateur): Observable<GestionUtilisateur> {
    return this.http.patch<GestionUtilisateur>(`${this.base}/${id}/`, data);
  }

  desactiver(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}/`);
  }
}
