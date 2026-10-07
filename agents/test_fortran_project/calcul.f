C     Calcul de la moyenne -- style FORTRAN 77, forme fixe
      DOUBLE PRECISION FUNCTION MOYENNE(T, N)
      DOUBLE PRECISION T(N)
      COMMON /STATS/ NAPPEL
      IF (N .LT. 1) STOP
      S = 0.0
      DO 10 I = 1, N
         S = S + T(I)
   10 CONTINUE
      NAPPEL = NAPPEL + 1
      MOYENNE = S / N
      END
