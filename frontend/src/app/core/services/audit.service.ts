import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { FiltresAudit, LigneAudit, PageApi } from '../models/accounts-admin.models';

@Injectable({ providedIn: 'root' })
export class AuditService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/journal-audit`;

  lister(filtres: FiltresAudit): Observable<PageApi<LigneAudit>> {
    let params = this.parametres(filtres).set('page', filtres.page);
    return this.http.get<PageApi<LigneAudit>>(`${this.base}/`, { params });
  }

  exporter(filtres: FiltresAudit): Observable<Blob> {
    return this.http.get(`${this.base}/export/`, {
      params: this.parametres(filtres),
      responseType: 'blob',
    });
  }

  private parametres(filtres: FiltresAudit): HttpParams {
    let params = new HttpParams();
    if (filtres.search) params = params.set('search', filtres.search);
    if (filtres.action) params = params.set('action', filtres.action);
    if (filtres.depuis) params = params.set('depuis', filtres.depuis);
    if (filtres.jusqua) params = params.set('jusqua', filtres.jusqua);
    return params;
  }
}
