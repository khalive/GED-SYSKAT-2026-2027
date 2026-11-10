import { ValidatorFn } from '@angular/forms';

/** Vérifie que deux champs d'un groupe ont la même valeur. */
export function correspondance(champ: string, confirmation: string): ValidatorFn {
  return (groupe) => {
    const a = groupe.get(champ)?.value;
    const b = groupe.get(confirmation)?.value;
    return a && b && a !== b ? { correspondance: true } : null;
  };
}
