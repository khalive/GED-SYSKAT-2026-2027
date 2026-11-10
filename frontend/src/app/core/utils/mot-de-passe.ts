export interface ForceMotDePasse {
  niveau: 0 | 1 | 2 | 3 | 4;
  libelle: string;
}

const LIBELLES = ['', 'Faible', 'Moyen', 'Bon', 'Excellent'];

/** Estimation indicative. La vraie validation reste celle du backend Django. */
export function forceMotDePasse(valeur: string): ForceMotDePasse {
  if (!valeur) return { niveau: 0, libelle: '' };
  if (valeur.length < 8) return { niveau: 1, libelle: 'Trop court' };
  let points = 1;
  if (valeur.length >= 12) points++;
  if (/[a-z]/.test(valeur) && /[A-Z]/.test(valeur)) points++;
  if (/\d/.test(valeur) && /[^A-Za-z0-9]/.test(valeur)) points++;
  const niveau = Math.min(points, 4) as 1 | 2 | 3 | 4;
  return { niveau, libelle: LIBELLES[niveau] };
}
