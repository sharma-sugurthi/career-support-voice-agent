import { headers } from 'next/headers';
import { getAppConfig } from '@/lib/utils';

interface LayoutProps {
  children: React.ReactNode;
}

export default async function Layout({ children }: LayoutProps) {
  const hdrs = await headers();
  const { companyName, logo, logoDark } = await getAppConfig(hdrs);

  return (
    <>
      <header className="fixed top-0 left-0 z-50 hidden w-full flex-row justify-between p-6 md:flex">
        <a href="#" className="scale-100 transition-transform duration-300 hover:scale-110">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={logo} alt={`${companyName} Logo`} className="block size-16 dark:hidden" />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={logoDark ?? logo}
            alt={`${companyName} Logo`}
            className="hidden size-16 dark:block"
          />
        </a>
      </header>
      <footer className="fixed bottom-0 left-0 z-50 hidden w-full justify-center p-4 md:flex">
        <span className="text-foreground font-mono text-xs font-bold tracking-wider uppercase">
          Open source&nbsp;
          <a
            href="https://github.com/sharma-sugurthi/career-support-voice-agent"
            target="_blank"
            rel="noreferrer"
            className="underline underline-offset-4"
          >
            Star on GitHub
          </a>
          &nbsp;|&nbsp;
          <a
            href="https://github.com/sponsors/sharma-sugurthi"
            target="_blank"
            rel="noreferrer"
            className="underline underline-offset-4"
          >
            Sponsor
          </a>
        </span>
      </footer>

      {children}
    </>
  );
}
