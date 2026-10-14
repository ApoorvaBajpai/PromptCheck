import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PromptCheck | Continuous Prompt Testing & Evaluation",
  description: "Prompt regression testing and quality assurance platform for AI applications.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background text-foreground antialiased selection:bg-primary/20 selection:text-primary">
        {children}
      </body>
    </html>
  );
}
