import { PropsUIRadioItem } from "../../../../types/elements";
import RadioSvg from "../../../../../assets/images/radio.svg";
import RadioActiveSvg from "../../../../../assets/images/radio_active.svg";
import { JSX } from "react";
import React from "react";

export const RadioItem = ({
  id,
  value,
  selected,
  onSelect,
}: PropsUIRadioItem): JSX.Element => {
  // This was a plain onClick div with role="checkbox" (wrong role for a
  // radio-group item) and no way to reach it from a keyboard — an
  // unlabeled group of these was neither operable nor announced
  // correctly to assistive tech. tabIndex + onKeyDown(Enter/Space) make
  // it keyboard-operable; role="radio" matches what this actually is.
  // Kiosk touch target also enlarged (min ~44px tall) — the original
  // hit area was just the icon+label's natural size, smaller than a
  // reliable fingertip target on a tablet.
  const handleKeyDown = (event: React.KeyboardEvent): void => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect();
    }
  };

  return (
    <div
      id={`${id}`}
      data-testid={`radio-${id}`}
      className="radio-item flex min-h-44px flex-row gap-3 items-center cursor-pointer py-2"
      onClick={onSelect}
      onKeyDown={handleKeyDown}
      role="radio"
      tabIndex={0}
      aria-checked={selected ? "true" : "false"}
    >
      <div>
        <img
          src={RadioSvg}
          id={`${id}-off`}
          className={selected ? "hidden" : ""}
        />
        <img
          src={RadioActiveSvg}
          id={`${id}-on`}
          className={selected ? "" : "hidden"}
        />
      </div>
      <div className="text-grey1 text-label font-label select-none mt-1">
        {value}
      </div>
    </div>
  );
};
