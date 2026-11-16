import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  PageApi,
  PermissionMetier,
  PermissionWrite,
  RoleGestion,
  RoleWrite,
} from '../models/accounts-admin.models';

@Injectable({ providedIn: 'root' })
export class RolesService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiUrl;

  roles(search = ''): Observable<PageApi<RoleGestion>> {
    let params = new HttpParams().set('page', 1).set('page_size', 100);
    if (search) params = params.set('search', search);
    return this.http.get<PageApi<RoleGestion>>(`${this.base}/roles/`, { params });
  }

  permissions(search = ''): Observable<PageApi<PermissionMetier>> {
    let params = new HttpParams().set('page', 1).set('page_size', 100);
    if (search) params = params.set('search', search);
    return this.http.get<PageApi<PermissionMetier>>(`${this.base}/permissions/`, { params });
  }

  creerRole(data: RoleWrite): Observable<RoleGestion> {
    return this.http.post<RoleGestion>(`${this.base}/roles/`, data);
  }

  modifierRole(id: number, data: RoleWrite): Observable<RoleGestion> {
    return this.http.patch<RoleGestion>(`${this.base}/roles/${id}/`, data);
  }

  supprimerRole(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/roles/${id}/`);
  }

  creerPermission(data: PermissionWrite): Observable<PermissionMetier> {
    return this.http.post<PermissionMetier>(`${this.base}/permissions/`, data);
  }

  modifierPermission(id: number, data: PermissionWrite): Observable<PermissionMetier> {
    return this.http.patch<PermissionMetier>(`${this.base}/permissions/${id}/`, data);
  }

  supprimerPermission(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/permissions/${id}/`);
  }
}
