import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, catchError, finalize, map, of, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  ChangePasswordRequest,
  Langue,
  LoginRequest,
  LoginResponse,
  RefreshResponse,
  Utilisateur,MessageResponse, PasswordResetConfirmRequest , ProfilUpdateRequest
} from '../models/auth.models';
import { LangueService } from './langue.service';

const CLE_ACCESS = 'ged.access';
const CLE_REFRESH = 'ged.refresh';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly langueService = inject(LangueService);
  private readonly base = `${environment.apiUrl}/auth`;

  private readonly _accessToken = signal<string | null>(localStorage.getItem(CLE_ACCESS));
  private readonly _refreshToken = signal<string | null>(localStorage.getItem(CLE_REFRESH));
  private readonly _user = signal<Utilisateur | null>(null);

  readonly accessToken = this._accessToken.asReadonly();
  readonly refreshToken = this._refreshToken.asReadonly();
  readonly user = this._user.asReadonly();
  readonly isAuthenticated = computed(() => this._accessToken() !== null);

  login(credentials: LoginRequest): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${this.base}/login/`, credentials).pipe(
      tap((res) => {
        this.enregistrerJetons(res.access, res.refresh);
        this.definirUtilisateur(res.user);
      }),
    );
  }

  /** Obtient un nouveau jeton d'accès à partir du jeton de rafraîchissement. */
  refresh(): Observable<string> {
    return this.http
      .post<RefreshResponse>(`${this.base}/refresh/`, { refresh: this._refreshToken() })
      .pipe(
        tap((res) => {
          localStorage.setItem(CLE_ACCESS, res.access);
          this._accessToken.set(res.access);
        }),
        map((res) => res.access),
      );
  }

  logout(): void {
    const refresh = this._refreshToken();
    const terminer = () => this.expirerSession();
    if (!refresh) {
      terminer();
      return;
    }
    this.http
      .post(`${this.base}/logout/`, { refresh })
      .pipe(finalize(terminer))
      .subscribe({ error: () => {} });
  }

  /** Au démarrage de l'application : recharge le profil si un jeton existe. */
  restoreSession(): Observable<unknown> {
    if (!this._accessToken() && !this._refreshToken()) {
      return of(null);
    }
    return this.http.get<Utilisateur>(`${this.base}/me/`).pipe(
      tap((user) => this.definirUtilisateur(user)),
      catchError(() => {
        this.effacerSession();
        return of(null);
      }),
    );
  }

  changerLangue(langue: Langue): Observable<Utilisateur> {
    return this.http
      .patch<Utilisateur>(`${this.base}/me/`, { langue })
      .pipe(tap((user) => this.definirUtilisateur(user)));
  }

  changerMotDePasse(data: ChangePasswordRequest): Observable<void> {
    return this.http.post<void>(`${this.base}/change-password/`, data);
  }
  /** Réponse toujours identique, que l'e-mail existe ou non (anti-énumération). */
  demanderReinitialisation(email: string): Observable<MessageResponse> {
    return this.http.post<MessageResponse>(`${this.base}/password-reset/`, { email });
  }

  confirmerReinitialisation(data: PasswordResetConfirmRequest): Observable<void> {
    return this.http.post<void>(`${this.base}/password-reset/confirm/`, data);
  }

  modifierProfil(data: ProfilUpdateRequest): Observable<Utilisateur> {
    return this.http
      .patch<Utilisateur>(`${this.base}/me/`, data)
      .pipe(tap((user) => this.definirUtilisateur(user)));
  }
  hasPermission(code: string): boolean {
    return this._user()?.permissions.includes(code) ?? false;
  }

  /** Efface la session locale puis renvoie vers l'écran de connexion. */
  expirerSession(): void {
    this.effacerSession();
    this.router.navigate(['/login']);
  }

  private definirUtilisateur(user: Utilisateur): void {
    this._user.set(user);
    this.langueService.appliquer(user.langue);
  }

  private enregistrerJetons(access: string, refresh: string): void {
    localStorage.setItem(CLE_ACCESS, access);
    localStorage.setItem(CLE_REFRESH, refresh);
    this._accessToken.set(access);
    this._refreshToken.set(refresh);
  }

  private effacerSession(): void {
    localStorage.removeItem(CLE_ACCESS);
    localStorage.removeItem(CLE_REFRESH);
    this._accessToken.set(null);
    this._refreshToken.set(null);
    this._user.set(null);
  }
}
