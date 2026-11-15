import React, { useId } from "react";

interface InspectionSceneSvgProps {
  className?: string;
  ariaLabel?: string;
}

export const InspectionSceneSvg: React.FC<InspectionSceneSvgProps> = ({
  className = "h-full w-full",
  ariaLabel = "Illustrated robot workspace with a Duplo brick and good and defective trays",
}) => {
  const uid = useId().replace(/:/g, "");
  const bgId = `bg-${uid}`;
  const tableId = `table-${uid}`;
  const armId = `arm-${uid}`;
  const brickId = `brick-${uid}`;
  const lightId = `light-${uid}`;

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 900 440"
      preserveAspectRatio="xMidYMid slice"
      role="img"
      aria-label={ariaLabel}
      className={className}
    >
      <defs>
        <linearGradient id={bgId} x2="1" y2="1">
          <stop stopColor="#20211e" />
          <stop offset="1" stopColor="#101210" />
        </linearGradient>
        <linearGradient id={tableId} x2="0" y2="1">
          <stop stopColor="#41443d" />
          <stop offset="1" stopColor="#282b27" />
        </linearGradient>
        <linearGradient id={armId} x2="1" y2="1">
          <stop stopColor="#d8b47c" />
          <stop offset=".5" stopColor="#aa8250" />
          <stop offset="1" stopColor="#624e33" />
        </linearGradient>
        <linearGradient id={brickId} x2="0" y2="1">
          <stop stopColor="#d5aa67" />
          <stop offset="1" stopColor="#9a633b" />
        </linearGradient>
        <radialGradient id={lightId}>
          <stop stopColor="#71725e" stopOpacity=".3" />
          <stop offset="1" stopColor="#111" stopOpacity="0" />
        </radialGradient>
      </defs>
      <path fill={`url(#${bgId})`} d="M0 0H900V440H0z" />
      <path fill={`url(#${lightId})`} d="M0 0H900V440H0z" />
      <path d="M0 120L900 170V440H0z" fill={`url(#${tableId})`} />
      <ellipse cx="400" cy="362" rx="175" ry="23" fill="#000" opacity=".35" />
      <g opacity=".85">
        <path d="M652 228L799 242L773 315L624 296z" fill="#344039" stroke="#637265" />
        <path d="M652 218L799 232L773 304L624 285z" fill="#1f2722" stroke="#718675" />
        <path d="M664 235L779 245L760 286L642 275z" fill="#2d352f" />
        <path d="M631 331L778 345L755 409L608 390z" fill="#443532" stroke="#78605c" />
        <path d="M631 321L778 335L755 398L608 379z" fill="#2b211f" stroke="#8c6b63" />
        <path d="M644 340L758 349L743 382L628 370z" fill="#382b27" />
      </g>
      <g stroke="#161917" strokeLinejoin="round">
        <path d="M134 329L270 339L251 379L114 365z" fill="#323631" strokeWidth="3" />
        <path d="M160 309L236 315L229 352L153 346z" fill={`url(#${armId})`} strokeWidth="3" />
        <ellipse cx="195" cy="317" rx="38" ry="13" fill="#b39361" />
        <path
          d="M181 304L176 215Q177 198 197 194Q218 194 223 211L222 309z"
          fill={`url(#${armId})`}
          strokeWidth="4"
        />
        <circle cx="198" cy="217" r="27" fill="#252b26" strokeWidth="4" />
        <circle cx="198" cy="217" r="12" fill="#777b6d" />
        <circle cx="198" cy="217" r="4" fill="#1b201c" />
        <path
          d="M194 194L290 74Q308 60 327 72Q339 85 328 103L224 229z"
          fill={`url(#${armId})`}
          strokeWidth="4"
        />
        <path d="M211 190L300 83" stroke="#e6cda3" strokeWidth="5" opacity=".6" />
        <circle cx="310" cy="87" r="28" fill="#333930" strokeWidth="4" />
        <circle cx="310" cy="87" r="14" fill="#a1a28b" />
        <circle cx="310" cy="87" r="5" fill="#1c211c" />
        <path
          d="M333 77L453 140Q470 150 461 168Q452 182 435 174L317 107z"
          fill={`url(#${armId})`}
          strokeWidth="4"
        />
        <path d="M344 93L442 149" stroke="#e6cda3" strokeWidth="4" opacity=".6" />
        <circle cx="448" cy="158" r="22" fill="#30362e" strokeWidth="4" />
        <circle cx="448" cy="158" r="10" fill="#969d86" />
        <path d="M446 178L459 213L439 225L419 186z" fill={`url(#${armId})`} strokeWidth="3" />
        <path
          d="M438 217L423 245L443 258L450 244L441 238L451 223M457 213L478 237L464 251L455 240L464 235L449 223"
          fill="#767c6b"
          strokeWidth="4"
        />
        <path
          d="M218 229Q260 176 277 128Q283 104 298 93"
          fill="none"
          stroke="#101611"
          strokeWidth="6"
        />
        <path d="M330 110Q367 150 427 163" fill="none" stroke="#111812" strokeWidth="5" />
      </g>
      <g transform="translate(420 280)">
        <ellipse cx="35" cy="51" rx="60" ry="13" fill="#070907" opacity=".5" />
        <path d="M0 0L69 7L64 51L-6 43z" fill="#986c40" />
        <path d="M0 0L20 -18L90 -11L69 7z" fill="#dfb978" />
        <path d="M69 7L90 -11L83 32L64 51z" fill="#705233" />
        <g fill={`url(#${brickId})`} stroke="#bd945a">
          <ellipse cx="24" cy="-10" rx="12" ry="5" />
          <path d="M12 -10V-19Q24 -26 36 -18V-9" />
          <ellipse cx="24" cy="-19" rx="12" ry="5" />
          <ellipse cx="57" cy="-6" rx="12" ry="5" />
          <path d="M45 -6V-15Q57 -22 69 -14V-5" />
          <ellipse cx="57" cy="-15" rx="12" ry="5" />
        </g>
        <path d="M43 9L38 20L47 28L44 43" fill="none" stroke="#574432" strokeWidth="2" />
      </g>
      <g fill="none" stroke="#90b89d" strokeWidth="1.5">
        <path d="M392 258V244H411M505 244H524V260M524 342V354H506M411 354H392V338" />
        <path d="M450 299H464M457 292V306" opacity=".6" />
      </g>
      <g fill="#c5ccc0" fontFamily="monospace" fontSize="11">
        <text x="670" y="263">
          GOOD
        </text>
        <text x="651" y="366">
          DEFECTIVE
        </text>
      </g>
    </svg>
  );
};
