"use client";

import MuiStack, { type StackProps as MuiStackProps } from "@mui/material/Stack";
import type { SxProps, Theme } from "@mui/material/styles";

type StackProps = MuiStackProps & {
  justifyContent?: unknown;
  alignItems?: unknown;
  flexWrap?: unknown;
};

export default function Stack({ justifyContent, alignItems, flexWrap, sx, ...props }: StackProps) {
  return (
    <MuiStack
      useFlexGap
      {...props}
      sx={
        {
          justifyContent,
          alignItems,
          flexWrap,
          minWidth: 0,
          ...(typeof sx === "object" && sx ? sx : {}),
        } as SxProps<Theme>
      }
    />
  );
}
