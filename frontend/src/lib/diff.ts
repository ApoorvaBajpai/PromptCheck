// Pure TypeScript diff utility for visual side-by-side and line comparison

export interface DiffLine {
  type: "added" | "removed" | "unchanged";
  text: string;
  leftLineNumber?: number;
  rightLineNumber?: number;
}

export function computeLineDiff(original: string, modified: string): DiffLine[] {
  const origLines = (original || "").split("\n");
  const modLines = (modified || "").split("\n");

  const diff: DiffLine[] = [];
  let i = 0;
  let j = 0;
  let lineLeft = 1;
  let lineRight = 1;

  while (i < origLines.length || j < modLines.length) {
    if (i < origLines.length && j < modLines.length) {
      if (origLines[i] === modLines[j]) {
        diff.push({
          type: "unchanged",
          text: origLines[i],
          leftLineNumber: lineLeft++,
          rightLineNumber: lineRight++,
        });
        i++;
        j++;
      } else {
        // Look ahead to see if original line appears later in modified
        const foundInMod = modLines.slice(j).indexOf(origLines[i]);
        const foundInOrig = origLines.slice(i).indexOf(modLines[j]);

        if (foundInMod !== -1 && (foundInOrig === -1 || foundInMod <= foundInOrig)) {
          // Line added in modified
          diff.push({
            type: "added",
            text: modLines[j],
            rightLineNumber: lineRight++,
          });
          j++;
        } else {
          // Line removed from original
          diff.push({
            type: "removed",
            text: origLines[i],
            leftLineNumber: lineLeft++,
          });
          i++;
        }
      }
    } else if (i < origLines.length) {
      diff.push({
        type: "removed",
        text: origLines[i],
        leftLineNumber: lineLeft++,
      });
      i++;
    } else {
      diff.push({
        type: "added",
        text: modLines[j],
        rightLineNumber: lineRight++,
      });
      j++;
    }
  }

  return diff;
}
