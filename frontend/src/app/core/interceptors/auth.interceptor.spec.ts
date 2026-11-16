import { HttpClient, HttpErrorResponse, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';

import { authInterceptor } from './auth.interceptor';

describe('authInterceptor', () => {
  let httpClient: HttpClient;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    localStorage.setItem('ged.access', 'expired-access');
    localStorage.setItem('ged.refresh', 'refresh-token');

    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: Router, useValue: { navigate: () => Promise.resolve(true) } },
      ],
    });
    httpClient = TestBed.inject(HttpClient);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
    localStorage.removeItem('ged.access');
    localStorage.removeItem('ged.refresh');
  });

  it('fails all concurrent requests when the shared refresh token is rejected', () => {
    const errors: number[] = [];
    httpClient.get('/api/resource/one').subscribe({
      error: (error: HttpErrorResponse) => errors.push(error.status),
    });
    httpClient.get('/api/resource/two').subscribe({
      error: (error: HttpErrorResponse) => errors.push(error.status),
    });

    httpTesting.expectOne('/api/resource/one').flush(null, {
      status: 401,
      statusText: 'Unauthorized',
    });
    httpTesting.expectOne('/api/resource/two').flush(null, {
      status: 401,
      statusText: 'Unauthorized',
    });
    httpTesting.expectOne('/api/auth/refresh/').flush(
      { detail: 'Refresh token invalide.' },
      { status: 401, statusText: 'Unauthorized' },
    );

    expect(errors).toEqual([401, 401]);
  });

  it('does not expire the session when a retried API request fails', () => {
    let erreurApi = 0;
    httpClient.get('/api/resource').subscribe({
      error: (error: HttpErrorResponse) => (erreurApi = error.status),
    });

    httpTesting.expectOne('/api/resource').flush(null, {
      status: 401,
      statusText: 'Unauthorized',
    });
    httpTesting.expectOne('/api/auth/refresh/').flush({ access: 'new-access' });
    httpTesting
      .expectOne((request) => request.url === '/api/resource')
      .flush(null, { status: 500, statusText: 'Server Error' });

    expect(erreurApi).toBe(500);
    expect(localStorage.getItem('ged.access')).toBe('new-access');
  });
});
