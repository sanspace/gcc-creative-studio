/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { HttpClientTestingModule } from '@angular/common/http/testing';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {BrowserAnimationsModule} from '@angular/platform-browser/animations';



import { VtoComponent } from './vto.component';

import { MatIconModule } from '@angular/material/icon';

import { MatIconTestingModule } from '@angular/material/icon/testing';

import { MatStepperModule } from '@angular/material/stepper';

import { MatRadioModule } from '@angular/material/radio';

import { ReactiveFormsModule, FormsModule } from '@angular/forms';

import { MatProgressSpinnerModule } from '@angular/material/progress-spinner'; // Direct import for spinner

import { MatDialogModule } from '@angular/material/dialog'; // Direct import for dialog

import { MatCardModule } from '@angular/material/card';

describe('VtoComponent', () => {



  let component: VtoComponent;



  let fixture: ComponentFixture<VtoComponent>;



  beforeEach(async () => {



    await TestBed.configureTestingModule({



      declarations: [VtoComponent],



      imports: [

        HttpClientTestingModule,

        MatIconModule,

        MatIconTestingModule,

        MatStepperModule,

        MatRadioModule,

        ReactiveFormsModule,

        FormsModule,

        MatProgressSpinnerModule, // Direct import

        MatDialogModule, // Direct import

                MatCardModule, // Explicitly include MatCardModule

                BrowserAnimationsModule,

              ],



    }).compileComponents();



    fixture = TestBed.createComponent(VtoComponent);

    component = fixture.componentInstance;

    fixture.detectChanges();

  });



  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
