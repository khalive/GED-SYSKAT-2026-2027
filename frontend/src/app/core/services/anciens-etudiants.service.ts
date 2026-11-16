import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  InscriptionAncienEtudiant,
  ProfilAncienEtudiant,
} from '../models/accounts-admin.models';
import { MessageResponse } from '../models/auth.models';

@Injectable({ providedIn: 'root' })
export class AnciensEtudiantsService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/anciens-etudiants`;

  inscrire(data: InscriptionAncienEtudiant): Observable<MessageResponse> {
    return this.http.post<MessageResponse>(`${this.base}/inscription/`, data);
  }

  monProfil(): Observable<ProfilAncienEtudiant> {
    return this.http.get<ProfilAncienEtudiant>(`${this.base}/me/`);
  }

  modifierMonProfil(data: Partial<ProfilAncienEtudiant>): Observable<ProfilAncienEtudiant> {
    return this.http.patch<ProfilAncienEtudiant>(`${this.base}/me/`, data);
  }
}
