import * as React from "react";
import { Weak } from "../../../../helpers";
import { PropsUIRadioItem, Translatable } from "../../../../types/elements";
import TextBundle from "../../../../text_bundle";
import { Translator } from "../../../../translator";
import { ReactFactoryContext } from "../../factory";
import { PropsUIPromptRadioInput } from "../../../../types/prompts";
import { RadioItem } from "../elements/radio_item";
import { PrimaryButton } from "../elements/button";
import { JSX } from "react";

interface Copy {
  title: string;
  description: string;
  continueButton: string;
}

type Props = Weak<PropsUIPromptRadioInput> & ReactFactoryContext;

function prepareCopy({ title, description, locale }: Props): Copy {
  return {
    title: Translator.translate(title, locale),
    description: Translator.translate(description, locale),
    continueButton: Translator.translate(continueButtonLabel(), locale),
  };
}

export const RadioInput = (props: Props): JSX.Element => {
  const [selectedId, setSelectedId] = React.useState<number>(-1);
  const [waiting, setWaiting] = React.useState<boolean>(false);
  const [checked, setChecked] = React.useState<boolean>(false);

  const { items, resolve } = props;
  const { title, description, continueButton } = prepareCopy(props);

  function handleSelect(id: number): void {
    setSelectedId(id);
    setChecked(true);
  }

  function handleConfirm(): void {
    if (!waiting) {
      setWaiting(true);
      const item = items.at(selectedId);
      if (item !== undefined) {
        resolve?.({ __type__: "PayloadString", value: item.value });
      }
    }
  }

  function renderItems(items: PropsUIRadioItem[]): JSX.Element[] {
    return items.map((item, index) => (
      <RadioItem
        key={index}
        onSelect={() => handleSelect(index)}
        id={index}
        value={item.value}
        selected={selectedId === index}
      />
    ));
  }

  return (
    <>
      <div
        id="radio-group-title"
        className="text-title5 font-title5 sm:text-title4 sm:font-title4 lg:text-title3 lg:font-title3 text-grey1"
      >
        {title}
      </div>
      <div className="mt-8" />
      <div id="select-panel">
        <div
          id="radio-group-description"
          className="flex-wrap text-bodylarge font-body text-grey1 text-left"
        >
          {description}
        </div>
        <div className="mt-4" />
        <div>
          {/* Without role="radiogroup", the role="radio" items inside are
              announced as loose, unrelated controls with no sense of how
              many options there are or which set they belong to. The
              title and description carry the only text explaining the
              choice, so they're wired up as the group's accessible name
              and description rather than being left as visual-only text. */}
          <div
            id="radio-group"
            className="flex flex-col gap-3"
            role="radiogroup"
            aria-labelledby="radio-group-title"
            aria-describedby="radio-group-description"
          >
            {renderItems(items)}
          </div>
        </div>
      </div>
      <div className="mt-8" />
      <div className={`flex flex-row gap-4 ${checked ? "" : "opacity-30"}`}>
        <PrimaryButton
          label={continueButton}
          onClick={handleConfirm}
          enabled={checked}
          spinning={waiting}
        />
      </div>
    </>
  );
};

const continueButtonLabel = (): Translatable => {
  return new TextBundle().add("en", "Continue").add("nl", "Doorgaan");
};
