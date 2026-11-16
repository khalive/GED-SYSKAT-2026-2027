import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { BehaviorSubject, catchError, filter, switchMap, take, throwError } from 'rxjs';

import { environment } from '../../../environments/environment';
import { AuthService } from '../services/auth.service';

type ResultatRafraichissement =
  | { succes: true; jeton: string }
  | { succes: false; erreur: unknown };

let rafraichissementEnCours = false;
const resultatRafraichissement$ = new BehaviorSubject<ResultatRafraichissement | null>(null);

const avecJeton = (req: HttpRequest<unknown>, jeton: string) =>
  req.clone({ setHeaders: { Authorization: `Bearer ${jeton}` } });

const estRouteAuthPublique = (url: string) =>
  url.includes('/auth/login/') ||
  url.includes('/auth/register/') ||
  url.includes('/auth/refresh/') ||
  url.includes('/auth/password-reset/');

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);

  if (!req.url.startsWith(environment.apiUrl) || estRouteAuthPublique(req.url)) {
    return next(req);
  }

  const jeton = auth.accessToken();
  const requete = jeton ? avecJeton(req, jeton) : req;

  return next(requete).pipe(
    catchError((erreur) => {
      const nonAutorise = erreur instanceof HttpErrorResponse && erreur.status === 401;
      if (!nonAutorise || !auth.refreshToken()) {
        return throwError(() => erreur);
      }

      if (rafraichissementEnCours) {
        return resultatRafraichissement$.pipe(
          filter(
            (resultat): resultat is ResultatRafraichissement => resultat !== null,
          ),
          take(1),
          switchMap((resultat) =>
            resultat.succes
              ? next(avecJeton(req, resultat.jeton))
              : throwError(() => resultat.erreur),
          ),
        );
      }

      rafraichissementEnCours = true;
      resultatRafraichissement$.next(null);

      return auth.refresh().pipe(
        catchError((erreurRefresh) => {
          rafraichissementEnCours = false;
          resultatRafraichissement$.next({ succes: false, erreur: erreurRefresh });
          auth.expirerSession();
          return throwError(() => erreurRefresh);
        }),
        switchMap((nouveauJeton) => {
          rafraichissementEnCours = false;
          resultatRafraichissement$.next({ succes: true, jeton: nouveauJeton });
          return next(avecJeton(req, nouveauJeton));
        }),
      );
    }),
  );
};
