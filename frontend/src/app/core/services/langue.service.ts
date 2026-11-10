import { Injectable } from '@angular/core';
import { Langue } from '../models/auth.models';

@Injectable({ providedIn: 'root' })
export class LangueService {
/** Applique la langue et le sens d'écriture (arabe = droite vers gauche). */
appliquer(langue: Langue): void {
  document.documentElement.lang = langue;
document.documentElement.dir = langue === 'ar' ? 'rtl' : 'ltr';
}
}
