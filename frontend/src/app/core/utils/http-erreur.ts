import { HttpErrorResponse } from '@angular/common/http';
import { AbstractControl } from '@angular/forms';

/** Premier message exploitable renvoyé par l'API, sinon le texte de repli. */
export function messageApi(err: HttpErrorResponse, repli: string): string {
  if (err.status === 0) {
    return 'Serveur injoignable. Vérifiez que le backend est démarré.';
  }
  if (err.status === 429) {
    return 'Trop de tentatives. Réessayez plus tard.';
  }
  const corps = err.error;
  if (corps && typeof corps === 'object') {
    if (typeof corps.detail === 'string') {
      return corps.detail;
    }
    for (const valeur of Object.values(corps as Record<string, unknown>)) {
      if (typeof valeur === 'string') {
        return valeur;
      }
      if (Array.isArray(valeur) && typeof valeur[0] === 'string') {
        return valeur[0];
      }
    }
  }
  return repli;
}

/**
 * Affiche sous chaque champ l'erreur renvoyée par l'API pour ce champ.
 * Retourne true si au moins une erreur a été placée.
 */
export function appliquerErreursChamps(
  err: HttpErrorResponse,
  controles: Record<string, AbstractControl>,
): boolean {
  const corps = err.error;
  if (!corps || typeof corps !== 'object') return false;
  let applique = false;
  for (const [cle, controle] of Object.entries(controles)) {
    const valeur = (corps as Record<string, unknown>)[cle];
    const message = Array.isArray(valeur)
      ? valeur.filter((v) => typeof v === 'string').join(' ')
      : typeof valeur === 'string'
        ? valeur
        : '';
    if (message) {
      controle.setErrors({ serveur: message });
      controle.markAsTouched();
      applique = true;
    }
  }
  return applique;
}
