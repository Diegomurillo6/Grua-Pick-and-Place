#include <ESP32Servo.h>

// === Pines motores paso a paso ===
const int DIR_VERTICAL = 32;
const int STEP_VERTICAL = 33;
const int DIR_HORIZONTAL = 26;
const int STEP_HORIZONTAL = 27;

// === Servo garra ===
Servo miServo;
const int pinServo = 2;

// === Sensores ultrasónicos ===
const int TRIG_GARRA = 18;
const int ECHO_GARRA = 15;
const int TRIG_TORRE_01 = 14, ECHO_TORRE_01 = 25;
const int TRIG_TORRE_10 = 5, ECHO_TORRE_10 = 4;
const int TRIG_TORRE_11 = 12, ECHO_TORRE_11 = 13;

// === Variables ===
bool Paso = false;
int DistanciaX = 0;
int DistanciaY = 0;

//Pin directo a Rasp
const int enciende_apaga = 23;

//inicialización de puertos 
void setup() {
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, 16, 17);  // RX=16, TX=17

  pinMode(DIR_VERTICAL, OUTPUT);
  pinMode(STEP_VERTICAL, OUTPUT);
  pinMode(DIR_HORIZONTAL, OUTPUT);
  pinMode(STEP_HORIZONTAL, OUTPUT);

  miServo.attach(pinServo);

  pinMode(TRIG_GARRA, OUTPUT);
  pinMode(ECHO_GARRA, INPUT);
  pinMode(TRIG_TORRE_01, OUTPUT); pinMode(ECHO_TORRE_01, INPUT);
  pinMode(TRIG_TORRE_10, OUTPUT); pinMode(ECHO_TORRE_10, INPUT);
  pinMode(TRIG_TORRE_11, OUTPUT); pinMode(ECHO_TORRE_11, INPUT);

  pinMode(enciende_apaga, INPUT);
  //movimiento inicial
  delay(5000);
  MoverY(2200, "arriba");
  Garra("abrir");
}
//Programa general
void loop() {
  int TorreBodega = Torre0();
  int TorreBanano = Torres("torre1");
  int TorreCafe = Torres("torre2");
  int TorreDispMedicos = Torres("torre3");

  //Prints para verificacion en el monitor serial, se pueden quitar
  Serial.print("TorreBodega: "); Serial.print(TorreBodega); Serial.println(leerDistancia(TRIG_GARRA, ECHO_GARRA));
  Serial.print("TorreBanano: "); Serial.print(TorreBanano); Serial.println(leerDistancia(TRIG_TORRE_01, ECHO_TORRE_01));
  Serial.print("TorreCafe: "); Serial.print(TorreCafe); Serial.println(leerDistancia(TRIG_TORRE_10, ECHO_TORRE_10));
  Serial.print("TorreDispMedicos: "); Serial.print(TorreDispMedicos); Serial.println(leerDistancia(TRIG_TORRE_11, ECHO_TORRE_11));

  //manda a la rasp cuantas cajas hay en cada torre
  Serial2.println(String(String(TorreCafe) + String(TorreBanano) + String(TorreDispMedicos)));

  //revisa condiciones de STANDBY
  if (TorreBodega == 0){
    Serial2.println("STBY");
  }
  if (TorreBanano == 5 && TorreCafe == 5 && TorreDispMedicos == 5){
    Serial2.println("STBY");
  }

  //revisa si esta en ON y se puede ejecutar
  if (digitalRead(enciende_apaga) == HIGH && (TorreBanano < 5 || TorreCafe < 5 || TorreDispMedicos < 5)){
    if (TorreBodega > 0){
      MoverY((7 - TorreBodega) * 350 + 100, "abajo"); //baja para leer qr

      // Solicitar lectura de QR
      Serial2.println("SCAN");
      int QR = categoria();
      delay(1000);
      switch (QR){ //dependiendo del qr pregunta si hay campo a ver si continua o si para
        case 2:
          if (TorreBanano < 5){
            Serial2.println("RUN");
            Garra("cerrar");
            DistanciaY = TorreBanano;
            DistanciaX = 1;
            Paso = true;
            break;
          }
          Serial2.println("STBY");
          break;
        case 3:
          if (TorreCafe < 5){
            Serial2.println("RUN");
            Garra("cerrar");
            DistanciaY = TorreCafe;
            DistanciaX = 2;
            Paso = true;
            break;
          }
          Serial2.println("STBY");
          break;
        case 1:
          if (TorreDispMedicos < 5){
            Serial2.println("RUN");
            Garra("cerrar");
            DistanciaY = TorreDispMedicos;
            DistanciaX = 3;
            Paso = true;
            break;
          }
          Serial2.println("STBY");
          break;
        default:
          Serial.println("QR no válido o no recibido");
          break;
      }
      MoverY((7 - TorreBodega) * 350 + 100, "arriba"); //sube a la posicion de inicio con o sin caja
    }

    if (Paso == true) { //si tiene caja entra para ir a dejarla
      //mavimiento definido para dejar todas las cajas
      MoverY(350, "abajo");
      MoverX(DistanciaX, "derecha");
      MoverY((5 - DistanciaY) * 350 + 100, "abajo");
      Garra("abrir");
      MoverY((5 - DistanciaY) * 350 + 100, "arriba");
      MoverX(DistanciaX, "izquierda");
      MoverY(350, "arriba");
      Paso = false;
    }
  }
}

int categoria() { //se encarga de recibir el codigo del qr
  String qr = "";
  
  while (true) {
    if (Serial2.available()) {
      qr = Serial2.readStringUntil('\n');
      qr.trim();

      if (qr.length() == 0) {
        // Ignorar entradas vacías
        continue;
      }

      Serial.print("QR recibido: ");
      Serial.println(qr);

      if (qr == "01") return 1;
      else if (qr == "10") return 2;
      else if (qr == "11") return 3;
      else {
        Serial.println("QR inválido recibido, esperando otro...");
        // Vuelve a esperar un QR válido
        qr = "";
        continue;
      }
    }
  }
}


long leerDistancia(int trigPin, int echoPin) { //mide la distancia de los ultrasonicos
  const int N = 11;
  long lecturas[N];
  for (int i = 0; i < N; i++) {
    digitalWrite(trigPin, LOW); delayMicroseconds(2);
    digitalWrite(trigPin, HIGH); delayMicroseconds(10);
    digitalWrite(trigPin, LOW);
    long duracion = pulseIn(echoPin, HIGH, 20000);
    long distancia = duracion * 0.034 / 2;
    lecturas[i] = distancia;
    delay(10);
  }

  for (int i = 0; i < N - 1; i++) {
    for (int j = i + 1; j < N; j++) {
      if (lecturas[j] < lecturas[i]) {
        long temp = lecturas[i];
        lecturas[i] = lecturas[j];
        lecturas[j] = temp;
      }
    }
  }

  return lecturas[N / 2];
}

int Torres(char* torre) { //transforma la distancia a cantidad de cajas
  long distancia = 0;
  if (torre == "torre1") distancia = leerDistancia(TRIG_TORRE_01, ECHO_TORRE_01);
  if (torre == "torre2") distancia = leerDistancia(TRIG_TORRE_10, ECHO_TORRE_10);
  if (torre == "torre3") distancia = leerDistancia(TRIG_TORRE_11, ECHO_TORRE_11);

  if (distancia < 18) return 5;
  else if (18 <= distancia && distancia < 23) return 4;
  else if (23 <= distancia && distancia < 28) return 3;
  else if (28 <= distancia && distancia < 33) return 2;
  else if (33 <= distancia && distancia < 38) return 1;
  else if (38 <= distancia) return 0;
}

int Torre0() { //transforma la distancia a cantidad de cajas
  long distancia = leerDistancia(TRIG_GARRA, ECHO_GARRA);
  if (distancia < 14) return 5;
  else if (14 <= distancia && distancia < 19) return 4;
  else if (19 <= distancia && distancia < 24) return 3;
  else if (24 <= distancia && distancia < 29) return 2;
  else if (29 <= distancia && distancia < 34) return 1;
  else if (34 <= distancia) return 0;
}

void MoverY(int pasos, char* dir) { //movimiento vertical
  if (strcmp(dir, "abajo") == 0) digitalWrite(DIR_VERTICAL, HIGH);
  else if (strcmp(dir, "arriba") == 0) digitalWrite(DIR_VERTICAL, LOW);
  delay(100);
  for (int i = 0; i < pasos; i++) {
    digitalWrite(STEP_VERTICAL, HIGH);
    delayMicroseconds(800);
    digitalWrite(STEP_VERTICAL, LOW);
    delayMicroseconds(800);
  }
}

void MoverX(int torre, char* dir) { //movimiento horizontal
  int pasos = 0;
  if (torre == 1) pasos = 15000;
  else if (torre == 2) pasos = 29000;
  else if (torre == 3) pasos = 43000;
  else return;

  if (strcmp(dir, "derecha") == 0) digitalWrite(DIR_HORIZONTAL, HIGH);
  else if (strcmp(dir, "izquierda") == 0) digitalWrite(DIR_HORIZONTAL, LOW);

  delay(100);
  for (int i = 0; i < pasos; i++) {
    digitalWrite(STEP_HORIZONTAL, HIGH);
    delayMicroseconds(400);
    digitalWrite(STEP_HORIZONTAL, LOW);
    delayMicroseconds(400);
  }
}

void Garra(char* dir) { //abre o cierra la garra
  if (strcmp(dir, "cerrar") == 0) miServo.write(180);
  else if (strcmp(dir, "abrir") == 0) miServo.write(0);
  delay(300);
}
