import React from "react";
import { Composition, registerRoot } from "remotion";
import { MarketingFilm, type FilmProps } from "./Film";
import { PiiFilm } from "./PiiFilm";
import { PiiCallFirst } from "./PiiCallFirst";
import { PiiLaunch } from "./PiiLaunch";
import { LaunchFilm } from "./launch/LaunchFilm";
import { setProduct } from "./brand";

const Film: React.FC<FilmProps> = (props) => {
  setProduct(props.product, props.module);
  return props.filmKind === "launch" ? <LaunchFilm {...props} /> : props.filmKind === "pii-call-first" ? <PiiCallFirst {...props} /> : props.filmKind === "pii-storyboard" ? <PiiFilm {...props} /> : props.filmKind === "pii-launch" ? <PiiLaunch {...props} /> : <MarketingFilm {...props} />;
};

const defaults: FilmProps = { title: "Product", scenes: [], durationInFrames: 1800, portrait: false };
const Root = () => <Composition id="MarketingFilm" component={Film} fps={30} width={1920} height={1080}
  durationInFrames={1800} defaultProps={defaults}
  calculateMetadata={({ props }) => ({ durationInFrames: props.durationInFrames, width: props.portrait ? 1080 : 1920, height: props.portrait ? 1920 : 1080 })} />;
registerRoot(Root);
