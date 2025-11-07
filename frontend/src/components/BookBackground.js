import React from 'react';
import { useTheme } from '../contexts/ThemeContext';

const BookBackground = () => {
  const { isDarkMode } = useTheme();

  // Single book component as SVG pattern
  const BookPattern = ({ x, y, rotation = 0 }) => (
    <g transform={`translate(${x}, ${y}) rotate(${rotation}, 80, 60)`}>
      {/* Simplified open book */}
      <path
        d="M 10 20 Q 8 22 10 100 L 70 100 Q 73 98 75 95 L 75 20 Q 73 18 70 18 L 15 18 Q 12 19 10 20 Z"
        fill="none"
        stroke={isDarkMode ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.4)'}
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M 75 20 L 75 95 Q 78 98 85 100 L 145 100 Q 148 99 150 95 L 150 20 Q 148 18 145 18 L 80 18 Q 77 19 75 20 Z"
        fill="none"
        stroke={isDarkMode ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.4)'}
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <line x1="75" y1="18" x2="75" y2="100" stroke={isDarkMode ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.4)'} strokeWidth="1.5" />

      {/* Page lines */}
      <line x1="20" y1="35" x2="65" y2="35" stroke={isDarkMode ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.25)'} strokeWidth="1" />
      <line x1="20" y1="50" x2="65" y2="50" stroke={isDarkMode ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.25)'} strokeWidth="1" />
      <line x1="20" y1="65" x2="65" y2="65" stroke={isDarkMode ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.25)'} strokeWidth="1" />

      <line x1="85" y1="35" x2="140" y2="35" stroke={isDarkMode ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.25)'} strokeWidth="1" />
      <line x1="85" y1="50" x2="140" y2="50" stroke={isDarkMode ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.25)'} strokeWidth="1" />
      <line x1="85" y1="65" x2="140" y2="65" stroke={isDarkMode ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.25)'} strokeWidth="1" />
    </g>
  );

  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden opacity-15">
      <svg
        className="w-full h-full"
        xmlns="http://www.w3.org/2000/svg"
        preserveAspectRatio="xMidYMid slice"
      >
        {/* Row 1 */}
        <BookPattern x={20} y={10} rotation={-5} />
        <BookPattern x={200} y={30} rotation={8} />
        <BookPattern x={380} y={5} rotation={-3} />
        <BookPattern x={560} y={35} rotation={5} />
        <BookPattern x={740} y={15} rotation={-7} />
        <BookPattern x={920} y={40} rotation={6} />

        {/* Row 2 */}
        <BookPattern x={100} y={110} rotation={-8} />
        <BookPattern x={280} y={130} rotation={3} />
        <BookPattern x={460} y={105} rotation={-6} />
        <BookPattern x={640} y={125} rotation={9} />
        <BookPattern x={820} y={115} rotation={-4} />

        {/* Row 3 */}
        <BookPattern x={30} y={200} rotation={7} />
        <BookPattern x={210} y={220} rotation={-4} />
        <BookPattern x={390} y={195} rotation={5} />
        <BookPattern x={570} y={215} rotation={-8} />
        <BookPattern x={750} y={205} rotation={3} />
        <BookPattern x={930} y={230} rotation={-6} />

        {/* Row 4 */}
        <BookPattern x={120} y={300} rotation={-5} />
        <BookPattern x={300} y={320} rotation={8} />
        <BookPattern x={480} y={295} rotation={-3} />
        <BookPattern x={660} y={315} rotation={7} />
        <BookPattern x={840} y={305} rotation={-9} />

        {/* Row 5 */}
        <BookPattern x={50} y={390} rotation={4} />
        <BookPattern x={230} y={410} rotation={-7} />
        <BookPattern x={410} y={385} rotation={6} />
        <BookPattern x={590} y={405} rotation={-5} />
        <BookPattern x={770} y={395} rotation={8} />
        <BookPattern x={950} y={420} rotation={-3} />

        {/* Row 6 */}
        <BookPattern x={140} y={480} rotation={-6} />
        <BookPattern x={320} y={500} rotation={5} />
        <BookPattern x={500} y={475} rotation={-8} />
        <BookPattern x={680} y={495} rotation={3} />
        <BookPattern x={860} y={485} rotation={-4} />

        {/* Row 7 */}
        <BookPattern x={70} y={570} rotation={7} />
        <BookPattern x={250} y={590} rotation={-5} />
        <BookPattern x={430} y={565} rotation={9} />
        <BookPattern x={610} y={585} rotation={-7} />
        <BookPattern x={790} y={575} rotation={4} />
        <BookPattern x={970} y={600} rotation={-6} />

        {/* Additional scattered quills for decoration */}
        <g transform="translate(165, 85) rotate(25)">
          <path
            d="M 0 0 Q -1 5 -2 15 Q -2.5 20 -3 25 L -2 26 Q -1 20 0 15 Q 1 5 2 0 Z"
            fill="none"
            stroke={isDarkMode ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.3)'}
            strokeWidth="1"
          />
        </g>

        <g transform="translate(520, 175) rotate(-15)">
          <path
            d="M 0 0 Q -1 5 -2 15 Q -2.5 20 -3 25 L -2 26 Q -1 20 0 15 Q 1 5 2 0 Z"
            fill="none"
            stroke={isDarkMode ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.3)'}
            strokeWidth="1"
          />
        </g>

        <g transform="translate(85, 350) rotate(40)">
          <path
            d="M 0 0 Q -1 5 -2 15 Q -2.5 20 -3 25 L -2 26 Q -1 20 0 15 Q 1 5 2 0 Z"
            fill="none"
            stroke={isDarkMode ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.3)'}
            strokeWidth="1"
          />
        </g>

        <g transform="translate(720, 265) rotate(-20)">
          <path
            d="M 0 0 Q -1 5 -2 15 Q -2.5 20 -3 25 L -2 26 Q -1 20 0 15 Q 1 5 2 0 Z"
            fill="none"
            stroke={isDarkMode ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.3)'}
            strokeWidth="1"
          />
        </g>

        <g transform="translate(350, 450) rotate(30)">
          <path
            d="M 0 0 Q -1 5 -2 15 Q -2.5 20 -3 25 L -2 26 Q -1 20 0 15 Q 1 5 2 0 Z"
            fill="none"
            stroke={isDarkMode ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.3)'}
            strokeWidth="1"
          />
        </g>

        <g transform="translate(890, 540) rotate(-35)">
          <path
            d="M 0 0 Q -1 5 -2 15 Q -2.5 20 -3 25 L -2 26 Q -1 20 0 15 Q 1 5 2 0 Z"
            fill="none"
            stroke={isDarkMode ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.3)'}
            strokeWidth="1"
          />
        </g>
      </svg>
    </div>
  );
};

export default BookBackground;
