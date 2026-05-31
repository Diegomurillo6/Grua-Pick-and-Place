# Pick and Place crane project

This project was made for the microprocesors and microcontrollers class, for my mechatronics engineering degree. It consisted in a crane mechaninism that detected via machine vision with OpenCV between three types of boxes, each to be placed in a different position.


It used a combination of stepper motors and ultrasonic sensors to track both the position of the crane and the states of each pile of boxes. Once it detected a box in the picking position, as far as placing positions were not full, it moved to picked it, reading the qr in the box to determine the position to place it. Once again, logic determined if
the positioning could be performed based in the state of each pile of boxes (either having space or beeing full). Depending on that state it would wait for a space to be cleared, or move directly to the required position.

Also, it worked with a live updated user interface, that allowed to control START/STOP operations, view the current state of the crane (working, waiting, or idle), and keep track of the live inventory in each of the piles of boxes. 

Two codes are provided, one for the microcontroller ESP32 used to control the motors and the working logic in C++, and one for the microprocesor Raspberry Pi, used to handle the interface and the machine vision operations. The two devices worked with serial communication via UART.
