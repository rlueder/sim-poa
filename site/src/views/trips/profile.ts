import { type ProfileFile, PURPOSE_ORDER } from '../../data/edom';

export interface Row {
  [purpose: string]: number;
  slot: number;
}

export function profileRows(profile: ProfileFile): Row[] {
  return profile.slots.map((slot, i) => {
    const row: Row = { slot };
    for (const purpose of PURPOSE_ORDER) row[purpose] = profile.series[purpose]?.[i] ?? 0;
    return row;
  });
}
