import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { AuthService } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        AuthService,
      ],
    });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('submits the reset token and new password to the confirmation endpoint', () => {
    const payload = {
      uid: 'MTQ',
      token: 'signed-token',
      nouveau_mot_de_passe: 'NouveauMdp456!',
    };
    let completed = false;

    service.confirmerReinitialisation(payload).subscribe(() => {
      completed = true;
    });

    const request = http.expectOne('/api/auth/password-reset/confirm/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual(payload);
    request.flush(null, { status: 204, statusText: 'No Content' });
    expect(completed).toBe(true);
  });

  it('submits a public registration request without logging the user in', () => {
    const payload = {
      username: 'nadia-test',
      email: 'nadia@example.org',
      first_name: 'Nadia',
      last_name: 'Test',
      password: 'S3cur!tyRaven_94',
    };

    service.inscrire(payload).subscribe();

    const request = http.expectOne('/api/auth/register/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual(payload);
    request.flush({ detail: 'Demande reçue.' }, { status: 202, statusText: 'Accepted' });
    expect(service.isAuthenticated()).toBe(false);
  });
});
