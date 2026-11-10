import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { BehaviorSubject, catchError, filter, switchMap, take, throwError } from 'rxjs';

import { environment } from '../../../environments/environment';
import { AuthService } from '../services/auth.service';

let rafraichissementEnCours = false;
const nouveauJeton$ = new BehaviorSubject<string | null>(null);

const avecJeton = (req: HttpRequest<unknown>, jeton: string) =>
req.clone({ setHeaders: { Authorization: `Bearer ${jeton}` } });

const estRouteAuthPublique = (url: string) =>
url.includes('/auth/login/') || url.includes('/auth/refresh/') || url.includes('/auth/password-reset/');

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);

// On ne touche qu'aux appels vers notre API, hors login et refresh.
if (!req.url.startsWith(environment.apiUrl) || estRouteAuthPublique(req.url)) {
return next(req);
}

const jeton = auth.accessToken();
const requete = jeton ? avecJeton(req, jeton) : req;

return next(requete).pipe(
  catchError((erreur) => {
  const non_autorise = erreur instanceof HttpErrorResponse && erreur.status === 401;
if (!non_autorise || !auth.refreshToken()) {
return throwError(() => erreur);
}

// Un rafraîchissement est déjà en cours : on attend son résultat.
if (rafraichissementEnCours) {
return nouveauJeton$.pipe(
  filter((j): j is string => j !== null),
take(1),
switchMap((j) => next(avecJeton(req, j))),
);
}

rafraichissementEnCours = true;
nouveauJeton$.next(null);
return auth.refresh().pipe(
  switchMap((j) => {
  rafraichissementEnCours = false;
nouveauJeton$.next(j);
return next(avecJeton(req, j));
}),
catchError((e) => {
rafraichissementEnCours = false;
auth.expirerSession();
return throwError(() => e);
}),
);
}),
);
};
